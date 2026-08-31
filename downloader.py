from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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

    allowed_hosts = {
        "youtube.com", "www.youtube.com", "m.youtube.com",
        "music.youtube.com", "youtu.be",
    }

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"} or host not in allowed_hosts:
        raise InvalidYouTubeURLError(
            "La URL no parece ser un enlace válido de YouTube."
        )

    return url


def _get_cookie_file() -> str | None:
    explicit = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    candidates = [
        explicit,
        "/app/cookies.txt",
        "cookies.txt",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate

    return None


def _base_ydl_options() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "extractor_args": {
            "youtube": {
                # Evitamos depender exclusivamente del cliente web, que suele
                # ser el primero en recibir comprobaciones anti-bot.
                "player_client": ["android", "web"],
            }
        },
    }

    # bgutil-ytdlp-pot-provider se detecta automáticamente cuando está
    # instalado y su servidor escucha en el puerto local predeterminado 4416.
    # Para una URL distinta se configura con el argumento oficial del
    # proveedor externo, no como un po_token.
    pot_url = os.environ.get("YTDLP_POT_PROVIDER_URL", "").strip()
    if pot_url and pot_url != "http://127.0.0.1:4416":
        opts["extractor_args"]["youtube"]["pot"] = [
            f"youtubepot-bgutilhttp:base_url={pot_url}"
        ]

    cookie_file = _get_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    return opts


def _run_extract(url: str, download: bool = False, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_youtube_url(url)

    opts = _base_ydl_options()
    if extra:
        opts.update(extra)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=download)
    except Exception as exc:
        raise DownloadFailedError(str(exc)) from exc

    if not isinstance(info, dict):
        raise DownloadFailedError("YouTube no devolvió información válida del video.")

    return info


def _extract_info(url: str) -> dict[str, Any]:
    try:
        return _run_extract(url, download=False)
    except DownloadFailedError as exc:
        raise DownloadFailedError(
            "No se pudo obtener la información del video: "
            f"{exc}"
        ) from exc


def get_video_info(url: str) -> dict[str, Any]:
    info = _extract_info(url)

    normalized = {
        "id": info.get("id"),
        "title": info.get("title") or "audio",
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or url,
    }

    try:
        from palette import attach_palette, best_thumbnail_url

        if normalized["thumbnail"]:
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

        extra = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
            }],
        }

        info = _run_extract(url, download=True, extra=extra)

        title = info.get("title") or "audio"
        uploader = info.get("uploader") or info.get("channel") or ""

        files = sorted(temp_dir.glob(f"*.{audio_format}"))
        if not files:
            raise DownloadFailedError(
                "La descarga terminó, pero no se encontró el archivo de audio."
            )

        output_file = files[0]
        if not output_file.exists() or output_file.stat().st_size == 0:
            raise DownloadFailedError("Se generó un archivo de audio vacío.")

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

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
