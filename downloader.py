from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yt_dlp


SUPPORTED_FORMATS = {
    "mp3",
    "m4a",
    "opus",
    "wav",
}

ProgressCallback = Callable[[dict[str, Any]], None]


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
        "https://youtube.com/",
        "http://youtube.com/",
        "https://www.youtube.com/",
        "http://www.youtube.com/",
        "https://youtu.be/",
        "http://youtu.be/",
        "https://music.youtube.com/",
        "http://music.youtube.com/",
    )

    if not clean_url.startswith(allowed):
        raise InvalidYouTubeURLError(
            "La URL no parece ser un enlace válido de YouTube."
        )

    return url


def _get_cookie_file() -> str | None:
    """Return a usable cookies.txt path, if one is configured."""
    candidates = []

    configured = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if configured:
        candidates.append(Path(configured))

    # The upload endpoint in main.py stores cookies here.
    candidates.append(Path("/app/cookies.txt"))

    for path in candidates:
        if path.is_file():
            return str(path)

    # Render environment variables survive container recreation and are useful
    # when cookies.txt itself is not persisted on the container filesystem.
    b64 = os.environ.get("YTDLP_COOKIES_B64", "").strip()
    if b64:
        target = Path("/tmp/sonora-cookies-env.txt")
        try:
            target.write_bytes(base64.b64decode(b64, validate=True))
            target.chmod(0o600)
            if target.is_file() and target.stat().st_size:
                return str(target)
        except Exception:
            pass

    raw = os.environ.get("YTDLP_COOKIES")
    if raw:
        target = Path("/tmp/sonora-cookies-raw.txt")
        try:
            target.write_text(raw, encoding="utf-8")
            target.chmod(0o600)
            if target.is_file() and target.stat().st_size:
                return str(target)
        except Exception:
            pass

    return None


def _base_ydl_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        # The Docker image starts the matching bgutil HTTP provider on 4416.
        "extractor_args": {
            "youtubepot-bgutilhttp": {
                "base_url": "http://127.0.0.1:4416",
            },
        },
    }

    cookie_file = _get_cookie_file()
    if cookie_file:
        options["cookiefile"] = cookie_file

    return options


def _clean_info(info: dict[str, Any], fallback_url: str) -> dict[str, Any]:
    return {
        "id": info.get("id"),
        "title": info.get("title") or "audio",
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or fallback_url,
    }


def _extract_info(url: str) -> dict[str, Any]:
    options = _base_ydl_options()
    options.update({
        "skip_download": True,
    })

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadFailedError(f"yt-dlp no pudo obtener la información: {exc}") from exc
    except Exception as exc:
        raise DownloadFailedError(f"Error obteniendo información de YouTube: {exc}") from exc

    if not isinstance(info, dict):
        raise DownloadFailedError("yt-dlp no devolvió información válida del vídeo.")

    return info


def get_video_info(url: str) -> dict[str, Any]:
    validate_youtube_url(url)
    info = _extract_info(url)

    cleaned = _clean_info(info, url)

    # Preserve the existing palette/thumbnail processing used by the frontend.
    try:
        from palette import attach_palette, best_thumbnail_url

        if cleaned.get("thumbnail"):
            cleaned["thumbnail"] = best_thumbnail_url(cleaned)
        return attach_palette(cleaned)
    except Exception:
        return cleaned


def _find_downloaded_file(temp_dir: Path, audio_format: str) -> Path | None:
    preferred = list(temp_dir.rglob(f"*.{audio_format}"))
    preferred = [
        path for path in preferred
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if preferred:
        return max(preferred, key=lambda path: path.stat().st_mtime)

    candidates = [
        path for path in temp_dir.rglob("*")
        if path.is_file()
        and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def download_audio(
    url: str,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, str, str]:
    """Download and convert YouTube audio directly inside the Render container."""
    validate_youtube_url(url)

    audio_format = audio_format.lower().strip()
    if audio_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Formato no soportado: {audio_format}. "
            f"Usa uno de: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    info = _extract_info(url)
    title = info.get("title") or "audio"
    uploader = info.get("uploader") or info.get("channel") or ""

    temp_dir = Path(tempfile.mkdtemp(prefix="yt-audio-render-"))

    options = _base_ydl_options()
    options.update({
        "format": "bestaudio/best",
        "outtmpl": str(temp_dir / "%(title)s.%(ext)s"),
        "restrictfilenames": True,
        "windowsfilenames": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": "192",
            }
        ],
    })

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        output_file = _find_downloaded_file(temp_dir, audio_format)
        if output_file is None:
            raise DownloadFailedError(
                "yt-dlp terminó sin producir un archivo de audio."
            )

        if output_file.stat().st_size == 0:
            raise DownloadFailedError("El archivo de audio generado está vacío.")

        if progress_callback:
            try:
                progress_callback({
                    "status": "finished",
                    "filename": str(output_file),
                    "title": title,
                    "uploader": uploader,
                })
            except Exception:
                pass

        return output_file, title, uploader

    except DownloadFailedError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except yt_dlp.utils.DownloadError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadFailedError(f"yt-dlp no pudo descargar el audio: {exc}") from exc
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadFailedError(f"Error descargando el audio: {exc}") from exc
