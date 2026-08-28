from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


DISCOVERY_URL = os.getenv("INVIDIOUS_DISCOVERY_URL", "https://api.invidious.io/instances.json").strip()
TIMEOUT = max(8, int(os.getenv("INVIDIOUS_TIMEOUT", "15")))
TTL = max(60, int(os.getenv("INVIDIOUS_INSTANCE_TTL", "900")))

# Current official public list is intentionally short. Discovery is preferred,
# while these entries keep the fallback alive if the instances API is down.
BOOTSTRAP = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yt.chocolatemoo53.com",
    "https://invidious.tiekoetter.com",
    "https://invidious.f5.si",
]

_cache: list[str] = []
_cache_at = 0.0


def _discover(force: bool = False) -> list[str]:
    global _cache, _cache_at
    now = time.time()
    if _cache and not force and now - _cache_at < TTL:
        return _cache

    found: list[str] = []
    try:
        request = Request(
            DISCOVERY_URL,
            headers={"User-Agent": "Sonora/1.0", "Accept": "application/json"},
        )
        with urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        if isinstance(payload, list):
            for entry in payload:
                if not isinstance(entry, list) or len(entry) < 2:
                    continue
                name, info = entry[0], entry[1]
                if not isinstance(name, str) or not isinstance(info, dict):
                    continue
                uri = str(info.get("uri") or "https://" + name).rstrip("/")
                if not uri.startswith("https://"):
                    continue
                if not info.get("api", False):
                    continue
                if uri not in found:
                    found.append(uri)
    except Exception as exc:
        print(f"=== SONORA: Invidious discovery failed: {exc} ===", flush=True)

    _cache = list(dict.fromkeys(found + BOOTSTRAP))
    _cache_at = now
    print(f"=== SONORA: discovered {len(found)} Invidious API instances; {len(_cache)} total ===", flush=True)
    return _cache


def _video_id(url: str) -> str | None:
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/").split("/", 1)[0] or None
    return parse_qs(parsed.query).get("v", [None])[0]


def _get_video(instance: str, video_id: str) -> dict:
    endpoint = f"{instance}/api/v1/videos/{quote(video_id, safe='')}"
    request = Request(
        endpoint,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0 Safari/537.36",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"HTTP {response.status}")
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise RuntimeError("invalid JSON")
    return data


def _pick_audio(data: dict) -> dict:
    candidates: list[dict] = []
    for stream in data.get("adaptiveFormats", []) or []:
        if not isinstance(stream, dict) or not stream.get("url"):
            continue
        mime = str(stream.get("type") or "").lower()
        if mime.startswith("audio/") or stream.get("audioQuality"):
            candidates.append(stream)

    if not candidates:
        raise RuntimeError("no usable audio streams")

    def score(stream: dict) -> tuple[int, int]:
        try:
            bitrate = int(stream.get("bitrate") or 0)
        except (TypeError, ValueError):
            bitrate = 0
        # Prefer m4a/mp4 slightly because it is widely accepted by FFmpeg.
        container = str(stream.get("container") or "").lower()
        preferred = 1 if container in {"m4a", "mp4"} else 0
        return bitrate, preferred

    return max(candidates, key=score)


def download(url: str, workdir: Path, fmt: str, ffmpeg_convert) -> tuple[dict, list[Path]]:
    video_id = _video_id(url)
    if not video_id:
        raise RuntimeError("Could not determine YouTube video ID")

    last_exc: Exception | None = None
    tried: set[str] = set()

    for refresh_round in range(2):
        for instance in _discover(force=refresh_round == 1):
            if instance in tried:
                continue
            tried.add(instance)
            source = workdir / "invidious-source"
            output = workdir / f"invidious-audio.{fmt}"
            try:
                print(f"=== SONORA: Invidious download attempt {instance} ===", flush=True)
                data = _get_video(instance, video_id)
                stream = _pick_audio(data)
                stream_url = str(stream["url"])
                request = Request(
                    stream_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0 Safari/537.36",
                        "Accept": "*/*",
                        "Referer": instance + "/",
                    },
                )
                with urlopen(request, timeout=TIMEOUT) as response, source.open("wb") as destination:
                    while True:
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        destination.write(chunk)

                if not source.is_file() or source.stat().st_size == 0:
                    raise RuntimeError("empty audio stream")

                ffmpeg_convert(source, output, fmt)
                return {
                    "id": video_id,
                    "title": data.get("title") or "audio",
                    "uploader": data.get("author") or "",
                    "channel": data.get("author") or "",
                    "duration": data.get("lengthSeconds"),
                    "thumbnail": (
                        (data.get("videoThumbnails") or [{}])[0].get("url")
                        if isinstance(data.get("videoThumbnails"), list)
                        else None
                    ) or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "webpage_url": url,
                    "metadata_source": "invidious-fallback",
                    "invidious_instance": instance,
                }, [output]
            except Exception as exc:
                print(f"=== SONORA: Invidious download failed on {instance}: {exc} ===", flush=True)
                last_exc = exc
                for item in (source, output):
                    try:
                        item.unlink()
                    except OSError:
                        pass

    raise RuntimeError(f"All Invidious download attempts failed: {last_exc}")


def patch_worker(worker_module) -> None:
    original = worker_module._piped_download
    if getattr(original, "_sonora_invidious_patch", False):
        return

    def patched(url, workdir, fmt):
        try:
            return download(url, workdir, fmt, worker_module._ffmpeg_convert)
        except Exception as exc:
            print(f"=== SONORA: Invidious fallback failed, continuing with Piped: {exc} ===", flush=True)
            return original(url, workdir, fmt)

    patched._sonora_invidious_patch = True
    worker_module._piped_download = patched
