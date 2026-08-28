import base64
import json
import os
import shutil
import tempfile
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

# YouTube changes its extraction requirements frequently.  Keep clients
# isolated so one blocked client does not poison the next attempt.
PLAYER_CLIENTS = [
    item.strip()
    for item in os.getenv(
        "YTDLP_PLAYER_CLIENTS",
        "android_vr,web_embedded,web_safari,mweb",
    ).split(",")
    if item.strip()
]

FALLBACK_PLAYER_CLIENTS = [
    item.strip()
    for item in os.getenv(
        "YTDLP_FALLBACK_PLAYER_CLIENTS",
        "tv_simply",
    ).split(",")
    if item.strip()
]

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
    # Cookies are OFF by default.  This prevents an expired/stale browser
    # session from turning otherwise public videos into LOGIN_REQUIRED.
    if not USE_COOKIES:
        return None
    env_cookie_file = _ensure_env_cookie_file()
    if env_cookie_file:
        return env_cookie_file
    if COOKIES_FILE.is_file() and COOKIES_FILE.stat().st_size > 0:
        return COOKIES_FILE
    return None

def _base_options(player_clients: list[str], *, download: bool = False) -> dict:
    options = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "verbose": True,
        "force_ipv4": True,
        "retries": 4,
        "fragment_retries": 4,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "sleep_interval_requests": 1,
        "extractor_args": {
            "youtube": {
                "player_client": player_clients,
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
    options = _base_options(player_clients, download=True)

    # android_vr can still expose the legacy pre-merged format 18 even when
    # YouTube blocks the separate GVS audio formats.  Asking for 18 first lets
    # ffmpeg extract the audio from that file and avoids the failing audio-only
    # GVS request.  Other clients keep the normal best-audio selection.
    if player_clients == ["android_vr"]:
        requested_format = "18/best"
    else:
        requested_format = "bestaudio/best"

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

def _profiles() -> list[list[str]]:
    profiles: list[list[str]] = []
    for client in PLAYER_CLIENTS + FALLBACK_PLAYER_CLIENTS:
        if [client] not in profiles:
            profiles.append([client])
    return profiles

def _extract_info(url: str) -> dict:
    last_exc: Optional[Exception] = None

    for clients in _profiles():
        try:
            print(f"=== SONORA: metadata attempt with {clients[0]} ===", flush=True)
            with yt_dlp.YoutubeDL(ytdlp_info_options(clients)) as ydl:
                data = ydl.extract_info(url, download=False)
            if data:
                return data
        except Exception as exc:
            print(f"=== SONORA: metadata client {clients[0]} failed: {exc} ===", flush=True)
            last_exc = exc

    # oEmbed is intentionally metadata-only.  The browser player supplies the
    # duration on the frontend when yt-dlp cannot expose it.
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
            print(f"=== SONORA: download attempt with {clients[0]} ===", flush=True)
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
            print(f"=== SONORA: download client {clients[0]} failed: {exc} ===", flush=True)
            last_exc = exc
            for item in list(workdir.iterdir()):
                if item.is_file():
                    try:
                        item.unlink()
                    except OSError:
                        pass

    assert last_exc is not None
    raise last_exc

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "sonora-worker",
        "youtube": "render-local-worker",
        "player_clients": PLAYER_CLIENTS,
        "fallback_player_clients": FALLBACK_PLAYER_CLIENTS,
        "cookies_configured": _cookie_file() is not None,
        "cookies_enabled": USE_COOKIES,
        "pot_provider": BGUTIL_URL,
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cookies_configured": _cookie_file() is not None,
        "cookies_enabled": USE_COOKIES,
        "player_clients": PLAYER_CLIENTS,
        "fallback_player_clients": FALLBACK_PLAYER_CLIENTS,
        "pot_provider": BGUTIL_URL,
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
            media_type="application/octet-stream",
        )
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("worker:app", host="127.0.0.1", port=8787, reload=False)
