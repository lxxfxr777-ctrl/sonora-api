from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cobalt_client import CobaltDownloadError, enabled as cobalt_enabled, download as cobalt_download

SUPPORTED_FORMATS = {"mp3", "m4a", "opus", "wav"}
ProgressCallback = Callable[[dict[str, object]], None]


class InvalidYouTubeURLError(ValueError):
    pass


class DownloadFailedError(RuntimeError):
    pass


def validate_youtube_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise InvalidYouTubeURLError("La URL no puede estar vacía.")
    clean_url = url.lower()
    allowed = (
        "https://youtube.com/", "http://youtube.com/", "https://www.youtube.com/",
        "http://www.youtube.com/", "https://youtu.be/", "http://youtu.be/",
        "https://music.youtube.com/", "http://music.youtube.com/",
    )
    if not clean_url.startswith(allowed):
        raise InvalidYouTubeURLError("La URL no parece ser un enlace válido de YouTube.")
    return url


def _get_worker_url() -> str:
    if os.environ.get("SONORA_LOCAL_WORKER", "").strip().lower() in {"1", "true", "yes", "on"}:
        return "http://127.0.0.1:8787"
    worker_url = os.environ.get("WORKER_URL", "").strip()
    if not worker_url:
        raise DownloadFailedError("WORKER_URL no está configurada en Render.")
    worker_url = worker_url.rstrip("/")
    if not worker_url.startswith(("http://", "https://")):
        raise DownloadFailedError("WORKER_URL debe comenzar con http:// o https://.")
    return worker_url


def _get_worker_token() -> str:
    return os.environ.get("WORKER_TOKEN", "").strip()


def _build_headers(content_type: str = "application/json") -> dict[str, str]:
    headers = {"Content-Type": content_type, "Accept": "application/json"}
    token = _get_worker_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _worker_request(endpoint: str, payload: dict[str, object], timeout: int = 300) -> tuple[bytes, str]:
    worker_url = _get_worker_url()
    url = f"{worker_url}/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    request = Request(url=url, data=data, headers=_build_headers(), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Type", "") or ""
    except HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = str(exc)
        raise DownloadFailedError(f"Worker respondió HTTP {exc.code}: {error_body[:800]}") from exc
    except URLError as exc:
        raise DownloadFailedError(f"No se pudo conectar con el worker en {worker_url}. Detalles: {exc}") from exc
    except TimeoutError as exc:
        raise DownloadFailedError("El worker tardó demasiado en responder.") from exc
    except Exception as exc:
        raise DownloadFailedError(f"Error comunicándose con el worker: {exc}") from exc


def _decode_json_response(body: bytes) -> dict[str, object]:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise DownloadFailedError("El worker devolvió una respuesta que no es JSON válido.") from exc
    if not isinstance(data, dict):
        raise DownloadFailedError("El worker devolvió un JSON inválido.")
    return data


def _worker_info(url: str) -> dict[str, object]:
    body, content_type = _worker_request("/info", {"url": url}, timeout=120)
    if "application/json" not in content_type.lower():
        raise DownloadFailedError("El endpoint /info del worker no devolvió JSON.")
    data = _decode_json_response(body)
    if not data.get("ok"):
        raise DownloadFailedError(str(data.get("detail", "El worker no pudo obtener la información del vídeo.")))
    return data


def _oembed_info(url: str) -> dict[str, object] | None:
    try:
        endpoint = "https://www.youtube.com/oembed?url=" + quote(url, safe="") + "&format=json"
        request = Request(endpoint, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _video_id(url: str) -> str | None:
    try:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path.lstrip("/").split("/", 1)[0] or None
        return parse_qs(parsed.query).get("v", [None])[0]
    except Exception:
        return None


def _embed_duration(url: str) -> int | None:
    """Get duration from the public embed player without requiring cookies."""
    video_id = _video_id(url)
    if not video_id:
        return None

    candidates = (
        f"https://www.youtube.com/embed/{video_id}?hl=en",
        f"https://www.youtube-nocookie.com/embed/{video_id}?hl=en",
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
    }
    patterns = (
        re.compile(r'"lengthSeconds"\s*:\s*"?(\d+)'),
        re.compile(r'"approxDurationMs"\s*:\s*"(\d+)"'),
        re.compile(r'"lengthSeconds"\s*:\s*(\d+)'),
    )

    for endpoint in candidates:
        try:
            request = Request(endpoint, headers=headers, method="GET")
            with urlopen(request, timeout=12) as response:
                html = response.read().decode("utf-8", errors="replace")
            for pattern in patterns:
                match = pattern.search(html)
                if not match:
                    continue
                value = int(match.group(1))
                if "approxDurationMs" in pattern.pattern:
                    value //= 1000
                if value > 0:
                    return value
        except Exception:
            continue
    return None


def get_video_info(url: str) -> dict[str, object]:
    validate_youtube_url(url)
    info = _worker_info(url)
    title = info.get("title") or "audio"
    uploader = info.get("uploader") or info.get("channel") or ""
    thumbnail = info.get("thumbnail")
    duration = info.get("duration")
    if duration in (None, 0, "0", ""):
        duration = _embed_duration(url)

    try:
        from palette import attach_palette, best_thumbnail_url
        normalized = {
            "id": info.get("id"),
            "title": title,
            "duration": duration,
            "uploader": uploader,
            "thumbnail": best_thumbnail_url(info) if thumbnail else None,
            "webpage_url": info.get("webpage_url") or url,
        }
        return attach_palette(normalized)
    except Exception:
        return {
            "id": info.get("id"),
            "title": title,
            "duration": duration,
            "uploader": uploader,
            "thumbnail": thumbnail,
            "webpage_url": info.get("webpage_url") or url,
        }


def _cobalt_fallback(url: str, audio_format: str, temp_dir: Path) -> tuple[Path, str, str]:
    if not cobalt_enabled():
        raise DownloadFailedError("Cobalt no está configurado en Render (COBALT_URL vacío).")
    try:
        output_file, filename = cobalt_download(url, audio_format, temp_dir)
    except CobaltDownloadError as exc:
        raise DownloadFailedError(str(exc)) from exc

    stem = output_file.stem.strip() or "audio"
    info = _oembed_info(url) or {}
    title = str(info.get("title") or stem)
    uploader = str(info.get("author_name") or "")
    return output_file, title, uploader


def download_audio(url: str, audio_format: str = "mp3", progress_callback: ProgressCallback | None = None) -> tuple[Path, str, str]:
    validate_youtube_url(url)
    audio_format = audio_format.lower().strip()
    if audio_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Formato no soportado: {audio_format}. Usa uno de: {', '.join(sorted(SUPPORTED_FORMATS))}")

    temp_dir = Path(tempfile.mkdtemp(prefix="yt-audio-worker-"))
    errors: list[str] = []
    try:
        # Primary backend: self-hosted Cobalt + automatic YouTube session generator.
        if cobalt_enabled():
            try:
                print("=== SONORA: download attempt with Cobalt ===", flush=True)
                output_file, title, uploader = _cobalt_fallback(url, audio_format, temp_dir)
                if progress_callback:
                    try:
                        progress_callback({
                            "status": "finished",
                            "filename": str(output_file),
                            "title": title,
                            "uploader": uploader,
                            "backend": "cobalt",
                        })
                    except Exception:
                        pass
                return output_file, title, uploader
            except Exception as exc:
                errors.append(f"Cobalt: {exc}")
                print(f"=== SONORA: Cobalt download failed: {exc} ===", flush=True)
        else:
            errors.append("Cobalt: COBALT_URL no está configurada")
            print("=== SONORA: Cobalt is not configured; using yt-dlp worker ===", flush=True)

        # Secondary backend: existing local yt-dlp worker.
        try:
            body, content_type = _worker_request(
                "/download",
                {"url": url, "format": audio_format},
                timeout=600,
            )
            if "application/json" in content_type.lower():
                try:
                    error_data = _decode_json_response(body)
                    detail = error_data.get("detail", "El worker no pudo descargar el audio.")
                except Exception:
                    detail = body.decode("utf-8", errors="replace")[:800]
                raise DownloadFailedError(str(detail))

            output_file = temp_dir / f"audio.{audio_format}"
            output_file.write_bytes(body)
            if output_file.stat().st_size == 0:
                raise DownloadFailedError("El worker devolvió un archivo de audio vacío.")

            title = "audio"
            uploader = ""
            try:
                info = _worker_info(url)
                title = str(info.get("title") or title)
                uploader = str(info.get("uploader") or info.get("channel") or "")
            except Exception:
                meta = _oembed_info(url) or {}
                title = str(meta.get("title") or title)
                uploader = str(meta.get("author_name") or uploader)

            if progress_callback:
                try:
                    progress_callback({
                        "status": "finished",
                        "filename": str(output_file),
                        "title": title,
                        "uploader": uploader,
                        "backend": "yt-dlp",
                    })
                except Exception:
                    pass
            return output_file, title, uploader
        except Exception as exc:
            errors.append(f"yt-dlp: {exc}")
            print(f"=== SONORA: yt-dlp fallback failed: {exc} ===", flush=True)

        raise DownloadFailedError("No fue posible descargar el audio. " + " | ".join(errors))
    except DownloadFailedError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadFailedError(str(exc)) from exc
