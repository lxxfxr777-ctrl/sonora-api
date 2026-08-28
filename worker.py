from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="Sonora YouTube Worker")

WORKER_TOKEN = os.getenv("WORKER_TOKEN", "").strip()
ALLOWED_FORMATS = {"mp3": "mp3", "m4a": "m4a", "opus": "opus", "wav": "wav"}
COOKIES_FILE = Path(os.getenv("YTDLP_COOKIES_FILE", "/app/cookies.txt"))
BGUTIL_URL = os.getenv("YTDLP_POT_PROVIDER_URL", "http://127.0.0.1:4416").rstrip("/")
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "").strip()
YTDLP_COOKIES_B64 = os.getenv("YTDLP_COOKIES_B64", "").strip()
USE_COOKIES = os.getenv("YTDLP_USE_COOKIES", "false").strip().lower() in {"1", "true", "yes", "on"}

# Piped is a fallback only. It lets Sonora try another YouTube-facing
# infrastructure when Render's datacenter IP is rejected by YouTube.
PIPED_DISCOVERY_URL = os.getenv(
    "PIPED_DISCOVERY_URL",
    "https://raw.githubusercontent.com/TeamPiped/documentation/main/content/docs/public-instances/index.md",
).strip()
PIPED_INSTANCE_TTL = max(60, int(os.getenv("PIPED_INSTANCE_TTL", "600")))
PIPED_TIMEOUT = max(10, int(os.getenv("PIPED_TIMEOUT", "45")))
PIPED_INSTANCES_ENV = os.getenv("PIPED_API_INSTANCES", "").strip()

# These are only a last-resort bootstrap list. The service first tries to
# refresh the public Piped instance list from TeamPiped's documentation.
PIPED_BOOTSTRAP_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.nosebs.ru",
    "https://pipedapi-libre.kavin.rocks",
    "https://piped-api.privacy.com.de",
    "https://pipedapi.adminforge.de",
    "https://api.piped.yt",
    "https://pipedapi.drgns.space",
    "https://pipedapi.owo.si",
    "https://pipedapi.ducks.party",
    "https://piped-api.codespace.cz",
    "https://pipedapi.reallyaweso.me",
    "https://api.piped.private.coffee",
    "https://pipedapi.darkness.services",
    "https://pipedapi.orangenet.cc",
]

_piped_cache: list[str] = []
_piped_cache_at = 0.0

# YouTube currently recommends using mweb together with an external PO Token
# provider when the normal clients are blocked. bgutil generates that token
# locally, so this remains the primary downloader.
PLAYER_CLIENT_PROFILES = [
    ["mweb"],
    ["web_safari"],
    ["tv_embedded"],
    ["web_embedded"],
    ["android_vr"],
]

_profiles_env = os.getenv("YTDLP_PLAYER_PROFILES", "").strip()
if _profiles_env:
    PLAYER_CLIENT_PROFILES = [
        [part.strip() for part in group.split(",") if part.strip()]
        for group in _profiles_env.split(";")
        if group.strip()
    ] or PLAYER_CLIENT_PROFILES


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format: str = "mp3"


def check_token(authorization: Optional[str]) -> None:
    if not WORKER_TOKEN:
        return
    if authorization != f"Bearer {WORKER_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def clean_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    if not any(host in url for host in ("youtube.com/", "youtu.be/", "music.youtube.com/")):
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported")
    return url


def _ensure_env_cookie_file() -> Optional[Path]:
    if not YTDLP_COOKIES_B64:
        return None
    try:
        data = base64.b64decode(YTDLP_COOKIES_B64, validate=True)
    except Exception as exc:
        raise RuntimeError("YTDLP_COOKIES_B64 is not valid base64") from exc
    if not data:
        return None
    path = Path(tempfile.gettempdir()) / "sonora-ytdlp-cookies.txt"
    path.write_bytes(data)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _cookie_file() -> Optional[Path]:
    if not USE_COOKIES:
        return None
    env_cookie_file = _ensure_env_cookie_file()
    if env_cookie_file:
        return env_cookie_file
    if COOKIES_FILE.is_file() and COOKIES_FILE.stat().st_size > 0:
        return COOKIES_FILE
    return None


def _base_options(player_clients: list[str]) -> dict:
    options = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "verbose": True,
        "force_ipv4": True,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 2,
        "socket_timeout": 30,
        "sleep_interval": 3,
        "max_sleep_interval": 6,
        "sleep_interval_requests": 3,
        "extractor_args": {
            "youtube": {
                "player_client": player_clients,
                "player_skip": ["webpage"],
                "fetch_pot": "auto",
            },
            "youtubepot-bgutilhttp": {
                "base_url": BGUTIL_URL,
            },
        },
        "js_runtimes": {
            "deno": {
                "path": os.getenv("DENO_PATH", "/usr/local/bin/deno"),
            }
        },
    }

    cookie_file = _cookie_file()
    if cookie_file:
        options["cookiefile"] = str(cookie_file)

    if YTDLP_PROXY:
        options["proxy"] = YTDLP_PROXY

    return options


def ytdlp_info_options(player_clients: list[str]) -> dict:
    options = _base_options(player_clients)
    options["skip_download"] = True
    return options


def ytdlp_download_options(workdir: Path, fmt: str, player_clients: list[str]) -> dict:
    options = _base_options(player_clients)
    requested_format = "18/bestaudio/best" if player_clients == ["android_vr"] else "bestaudio/best"

    options.update({
        "outtmpl": str(workdir / "%(title).120s-%(id)s.%(ext)s"),
        "format": requested_format,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": ALLOWED_FORMATS[fmt],
            "preferredquality": "192",
        }],
    })
    return options


def _youtube_oembed(url: str) -> Optional[dict]:
    try:
        endpoint = "https://www.youtube.com/oembed?url=" + quote(url, safe="") + "&format=json"
        request = Request(endpoint, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _video_id(url: str) -> Optional[str]:
    try:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path.lstrip("/").split("/", 1)[0] or None
        return parse_qs(parsed.query).get("v", [None])[0]
    except Exception:
        return None


def _parse_piped_instances(markdown: str) -> list[str]:
    instances: list[str] = []
    for line in markdown.splitlines():
        if "|" not in line or "https://" not in line:
            continue
        for part in line.split("|"):
            value = part.strip().strip("`")
            if not value.startswith("https://"):
                continue
            # The public-instance table contains API URLs in this column.
            # Keep only Piped-looking API hosts and reject arbitrary links.
            host = value.split("/", 3)[2].lower()
            if any(marker in host for marker in ("pipedapi.", "piped-api.", "api.piped.", "pdapi.", "piapi.", "yapi.")):
                value = value.rstrip("/")
                if value not in instances:
                    instances.append(value)
    return instances


def _piped_instances(force_refresh: bool = False) -> list[str]:
    global _piped_cache, _piped_cache_at

    if PIPED_INSTANCES_ENV:
        configured = [item.strip().rstrip("/") for item in PIPED_INSTANCES_ENV.split(",") if item.strip()]
        return list(dict.fromkeys(configured + PIPED_BOOTSTRAP_INSTANCES))

    now = time.time()
    if _piped_cache and not force_refresh and now - _piped_cache_at < PIPED_INSTANCE_TTL:
        return _piped_cache

    discovered: list[str] = []
    try:
        request = Request(
            PIPED_DISCOVERY_URL,
            headers={"User-Agent": "Sonora/1.0", "Accept": "text/plain,text/markdown,*/*"},
            method="GET",
        )
        with urlopen(request, timeout=15) as response:
            markdown = response.read().decode("utf-8", errors="replace")
        discovered = _parse_piped_instances(markdown)
        print(f"=== SONORA: discovered {len(discovered)} Piped instances ===", flush=True)
    except Exception as exc:
        print(f"=== SONORA: Piped instance discovery failed: {exc} ===", flush=True)

    combined = list(dict.fromkeys(discovered + PIPED_BOOTSTRAP_INSTANCES))
    _piped_cache = combined
    _piped_cache_at = now
    return combined


def _piped_streams(video_id: str, instance: str) -> dict:
    endpoint = f"{instance.rstrip('/')}/streams/{quote(video_id, safe='')}"
    request = Request(
        endpoint,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Sonora/1.0)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=PIPED_TIMEOUT) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Piped HTTP {response.status}")
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise RuntimeError("Piped returned invalid JSON")
    return data


def _choose_audio_stream(data: dict) -> dict:
    streams = data.get("audioStreams")
    if not isinstance(streams, list):
        raise RuntimeError("Piped returned no audioStreams")

    valid = [
        stream for stream in streams
        if isinstance(stream, dict) and stream.get("url") and not stream.get("videoOnly", False)
    ]
    if not valid:
        raise RuntimeError("Piped returned no usable audio stream")

    def bitrate(stream: dict) -> int:
        try:
            return int(stream.get("bitrate") or 0)
        except (TypeError, ValueError):
            return 0

    return max(valid, key=bitrate)


def _piped_info(url: str) -> dict:
    video_id = _video_id(url)
    if not video_id:
        raise RuntimeError("Could not determine YouTube video ID")

    last_exc: Optional[Exception] = None
    instances = _piped_instances()
    for index, instance in enumerate(instances):
        try:
            print(f"=== SONORA: Piped metadata attempt {index + 1}/{len(instances)} {instance} ===", flush=True)
            data = _piped_streams(video_id, instance)
            return {
                "id": video_id,
                "title": data.get("title") or "audio",
                "uploader": data.get("uploader") or data.get("uploaderName") or "",
                "channel": data.get("uploader") or data.get("uploaderName") or "",
                "duration": data.get("duration"),
                "thumbnail": data.get("thumbnailUrl") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "webpage_url": url,
                "description": data.get("description"),
                "metadata_source": "piped-fallback",
                "piped_instance": instance,
            }
        except Exception as exc:
            print(f"=== SONORA: Piped instance failed: {instance}: {exc} ===", flush=True)
            last_exc = exc

    # Refresh once in case the public instance list changed while this
    # process was running.
    refreshed = _piped_instances(force_refresh=True)
    for instance in refreshed:
        if instance in instances:
            continue
        try:
            data = _piped_streams(video_id, instance)
            return {
                "id": video_id,
                "title": data.get("title") or "audio",
                "uploader": data.get("uploader") or data.get("uploaderName") or "",
                "channel": data.get("uploader") or data.get("uploaderName") or "",
                "duration": data.get("duration"),
                "thumbnail": data.get("thumbnailUrl") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "webpage_url": url,
                "description": data.get("description"),
                "metadata_source": "piped-fallback",
                "piped_instance": instance,
            }
        except Exception as exc:
            last_exc = exc

    raise RuntimeError(f"All Piped instances failed: {last_exc}")


def _ffmpeg_convert(input_path: Path, output_path: Path, fmt: str) -> None:
    codecs = {
        "mp3": ["-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", "192k"],
        "m4a": ["-vn", "-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"],
        "opus": ["-vn", "-map", "0:a:0", "-c:a", "libopus", "-b:a", "128k"],
        "wav": ["-vn", "-map", "0:a:0", "-c:a", "pcm_s16le"],
    }
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(input_path)]
    command.extend(codecs[fmt])
    command.append(str(output_path))
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "unknown ffmpeg error").strip()[-1500:]
        raise RuntimeError(f"FFmpeg conversion failed: {detail}")


def _piped_download(url: str, workdir: Path, fmt: str) -> tuple[dict, list[Path]]:
    video_id = _video_id(url)
    if not video_id:
        raise RuntimeError("Could not determine YouTube video ID")

    last_exc: Optional[Exception] = None
    instances = _piped_instances()
    tried = set()

    for refresh_round in range(2):
        for instance in _piped_instances(force_refresh=(refresh_round == 1)):
            if instance in tried:
                continue
            tried.add(instance)
            input_path = workdir / "piped-source"
            output_path = workdir / f"piped-audio.{fmt}"
            try:
                print(f"=== SONORA: Piped download attempt {instance} ===", flush=True)
                data = _piped_streams(video_id, instance)
                stream = _choose_audio_stream(data)
                stream_url = str(stream["url"])

                request = Request(
                    stream_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0 Safari/537.36",
                        "Accept": "*/*",
                        "Referer": "https://piped.video/",
                    },
                    method="GET",
                )
                with urlopen(request, timeout=PIPED_TIMEOUT) as response, input_path.open("wb") as destination:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        destination.write(chunk)

                if not input_path.is_file() or input_path.stat().st_size == 0:
                    raise RuntimeError("Piped returned an empty audio stream")

                _ffmpeg_convert(input_path, output_path, fmt)
                return {
                    "id": video_id,
                    "title": data.get("title") or "audio",
                    "uploader": data.get("uploader") or data.get("uploaderName") or "",
                    "channel": data.get("uploader") or data.get("uploaderName") or "",
                    "duration": data.get("duration"),
                    "thumbnail": data.get("thumbnailUrl") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "webpage_url": url,
                    "metadata_source": "piped-fallback",
                    "piped_instance": instance,
                }, [output_path]
            except Exception as exc:
                print(f"=== SONORA: Piped download failed on {instance}: {exc} ===", flush=True)
                last_exc = exc
                for item in (input_path, output_path):
                    try:
                        item.unlink()
                    except OSError:
                        pass

    raise RuntimeError(f"All Piped download attempts failed: {last_exc}")


def _profiles() -> list[list[str]]:
    profiles: list[list[str]] = []
    for profile in PLAYER_CLIENT_PROFILES:
        cleaned = [client for client in profile if client]
        if cleaned and cleaned not in profiles:
            profiles.append(cleaned)
    return profiles


def _extract_info(url: str) -> dict:
    last_exc: Optional[Exception] = None

    for clients in _profiles():
        try:
            print(f"=== SONORA: metadata attempt with {','.join(clients)} ===", flush=True)
            with yt_dlp.YoutubeDL(ytdlp_info_options(clients)) as ydl:
                data = ydl.extract_info(url, download=False)
            if data:
                return data
        except Exception as exc:
            print(f"=== SONORA: metadata client {','.join(clients)} failed: {exc} ===", flush=True)
            last_exc = exc

    try:
        return _piped_info(url)
    except Exception as exc:
        print(f"=== SONORA: Piped metadata fallback failed: {exc} ===", flush=True)
        last_exc = exc

    meta = _youtube_oembed(url)
    if meta and meta.get("title"):
        video_id = _video_id(url)
        return {
            "id": video_id,
            "title": meta.get("title"),
            "uploader": meta.get("author_name") or "",
            "channel": meta.get("author_name") or "",
            "duration": None,
            "thumbnail": meta.get("thumbnail_url") or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None),
            "webpage_url": url,
            "description": None,
            "metadata_source": "youtube-oembed-fallback",
            "yt_dlp_error": str(last_exc) if last_exc else None,
        }

    assert last_exc is not None
    raise last_exc


def _download_with_clients(url: str, workdir: Path, fmt: str) -> tuple[dict, list[Path]]:
    last_exc: Optional[Exception] = None

    for clients in _profiles():
        try:
            print(f"=== SONORA: download attempt with {','.join(clients)} + bgutil ===", flush=True)
            with yt_dlp.YoutubeDL(ytdlp_download_options(workdir, fmt, clients)) as ydl:
                data = ydl.extract_info(url, download=True)

            files = [
                p for p in workdir.iterdir()
                if p.is_file() and p.suffix.lower() == f".{fmt}"
            ]
            if files:
                return data, files
            raise RuntimeError("yt-dlp completed but no converted audio file was produced.")
        except Exception as exc:
            print(f"=== SONORA: download client {','.join(clients)} failed: {exc} ===", flush=True)
            last_exc = exc
            for item in list(workdir.iterdir()):
                if item.is_file():
                    try:
                        item.unlink()
                    except OSError:
                        pass

    # Important: Piped is a fallback, not a replacement. If YouTube rejects
    # Render's datacenter IP, the public Piped infrastructure gets the stream
    # and Sonora converts it locally with FFmpeg.
    try:
        return _piped_download(url, workdir, fmt)
    except Exception as exc:
        print(f"=== SONORA: Piped download fallback failed: {exc} ===", flush=True)
        last_exc = exc

    assert last_exc is not None
    raise last_exc


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "sonora-worker",
        "youtube": "local-yt-dlp-bgutil+piped-fallback",
        "player_profiles": PLAYER_CLIENT_PROFILES,
        "cookies_configured": _cookie_file() is not None,
        "cookies_enabled": USE_COOKIES,
        "pot_provider": BGUTIL_URL,
        "piped_instances": len(_piped_instances()),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cookies_configured": _cookie_file() is not None,
        "cookies_enabled": USE_COOKIES,
        "player_profiles": PLAYER_CLIENT_PROFILES,
        "pot_provider": BGUTIL_URL,
        "piped_instances": len(_piped_instances()),
    }


@app.post("/info")
def info(request: InfoRequest, authorization: Optional[str] = Header(default=None)):
    check_token(authorization)
    url = clean_url(request.url)
    try:
        data = _extract_info(url)
        return {
            "ok": True,
            "id": data.get("id"),
            "title": data.get("title"),
            "uploader": data.get("uploader"),
            "channel": data.get("channel"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "webpage_url": data.get("webpage_url") or url,
            "description": data.get("description"),
            "metadata_source": data.get("metadata_source", "yt-dlp"),
            "yt_dlp_error": data.get("yt_dlp_error"),
            "piped_instance": data.get("piped_instance"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/download")
def download(request: DownloadRequest, authorization: Optional[str] = Header(default=None)):
    check_token(authorization)
    url = clean_url(request.url)
    fmt = request.format.lower().strip()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported format. Use mp3, m4a, opus or wav.")

    workdir = Path(tempfile.mkdtemp(prefix="sonora-worker-"))
    try:
        data, files = _download_with_clients(url, workdir, fmt)
        audio_file = files[0]
        return FileResponse(
            path=str(audio_file),
            filename=f"{data.get('title') or 'audio'}.{fmt}",
            media_type="audio/mpeg" if fmt == "mp3" else ("audio/mp4" if fmt == "m4a" else ("audio/ogg" if fmt == "opus" else "audio/wav")),
        )
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("worker:app", host="127.0.0.1", port=8787, reload=False)
