from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp


SUPPORTED_FORMATS = {"mp3", "m4a", "opus", "wav"}


class InvalidYouTubeURLError(ValueError):
    pass


class DownloadFailedError(RuntimeError):
    pass


def validate_youtube_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise InvalidYouTubeURLError("La URL no puede estar vacía.")

    allowed_hosts = (
        "youtube.com", "www.youtube.com", "m.youtube.com",
        "youtu.be", "music.youtube.com",
    )

    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        host = ""

    if parsed.scheme not in {"http", "https"} or host not in allowed_hosts:
        raise InvalidYouTubeURLError(
            "La URL no parece ser un enlace válido de YouTube."
        )

    return url


def _get_cookie_file() -> str | None:
    explicit = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit

    default = Path("/app/cookies.txt")
    if default.is_file():
        return str(default)

    local = Path("cookies.txt")
    if local.is_file():
        return str(local)

    return None


def _base_ydl_options() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"],
            }
        },
    }

    pot_url = os.environ.get(
        "YTDLP_POT_PROVIDER_URL",
        "http://127.0.0.1:4416",
    ).strip()

    if pot_url:
        opts["extractor_args"]["youtube"]["po_token"] = [
            f"web+{pot_url}",
        ]

    cookie_file = _get_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    return opts


def _extract_info(url: str) -> dict[str, Any]:
    validate_youtube_url(url)

    try:
        with yt_dlp.YoutubeDL(_base_ydl_options()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadFailedError(
            f"No se pudo obtener la información del video: {exc}"
        ) from exc

    if not isinstance(info, dict):
        raise DownloadFailedError(
            "YouTube no devolvió información válida del video."
        )

    return info


def get_video_info(url: str) -> dict[str, Any]:
    info = _extract_info(url)

    thumbnail = info.get("thumbnail")
    normalized = {
        "id": info.get("id"),
        "title": info.get("title") or "audio",
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "thumbnail": thumbnail,
        "webpage_url": info.get("webpage_url") or url,
    }

    try:
        from palette import attach_palette, best_thumbnail_url

        if thumbnail:
            normalized["thumbnail"] = best_thumbnail_url(info)

        return attach_palette(normalized)
    except Exception:
        return normalized


def download_audio(
    url: str,
    audio_format: str = "mp3",
    progress_callback: Any = None,
) -> tuple[Path, str, str]:
    validate_youtube_url(url)

    audio_format = audio_format.lower().strip()
    if audio_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Formato no soportado: {audio_format}. "
            f"Usa uno de: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="yt-audio-"))

    try:
        output_template = str(temp_dir / "%(id)s.%(ext)s")

        opts = _base_ydl_options()
        opts.update({
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
            }],
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        title = info.get("title") or "audio"
        uploader = info.get("uploader") or info.get("channel") or ""

        files = sorted(temp_dir.glob(f"*.{audio_format}"))
        if not files:
            raise DownloadFailedError(
                "La descarga terminó, pero no se encontró el archivo de audio."
            )

        output_file = files[0]

        if not output_file.exists() or output_file.stat().st_size == 0:
            raise DownloadFailedError(
                "Se generó un archivo de audio vacío."
            )

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
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadFailedError(
            f"No se pudo descargar el audio: {exc}"
        ) from exc
