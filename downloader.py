from __future__ import annotations

from collections.abc import Callable
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError


SUPPORTED_FORMATS = {
    "mp3",
    "m4a",
    "opus",
    "wav",
}

THUMBNAIL_EMBED_FORMATS = {
    "mp3",
    "m4a",
    "opus",
}

ProgressCallback = Callable[[dict[str, Any]], None]


class InvalidYouTubeURLError(ValueError):
    pass


class DownloadFailedError(RuntimeError):
    pass


def validate_youtube_url(url: str) -> str:
    url = url.strip()

    if not url:
        raise InvalidYouTubeURLError(
            "La URL no puede estar vacía."
        )

    allowed = (
        "youtube.com/",
        "www.youtube.com/",
        "youtu.be/",
        "music.youtube.com/",
    )

    clean_url = url.lower()

    if not (
        clean_url.startswith("https://youtube.com/")
        or clean_url.startswith("http://youtube.com/")
        or clean_url.startswith("https://www.youtube.com/")
        or clean_url.startswith("http://www.youtube.com/")
        or clean_url.startswith("https://youtu.be/")
        or clean_url.startswith("http://youtu.be/")
        or clean_url.startswith("https://music.youtube.com/")
        or clean_url.startswith("http://music.youtube.com/")
    ):
        raise InvalidYouTubeURLError(
            "La URL no parece ser un enlace válido de YouTube."
        )

    return url


def _ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is not None:
        return

    possible_paths = (
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
    )

    for directory in possible_paths:
        ffmpeg_path = Path(directory) / "ffmpeg"

        if ffmpeg_path.exists():
            os.environ["PATH"] = (
                f"{directory}:{os.environ.get('PATH', '')}"
            )
            return

    raise DownloadFailedError(
        "ffmpeg no está instalado."
    )


def _base_ydl_options() -> dict[str, Any]:
    """
    Configuración común de yt-dlp.

    No forzamos clientes específicos de YouTube.
    Esto permite que yt-dlp seleccione la estrategia
    compatible disponible.
    """

    return {
        "quiet": False,
        "no_warnings": False,

        "format": "bestaudio/best",

        "retries": 3,
        "fragment_retries": 3,

        "force_ipv4": True,

        "js_runtimes": {
            "deno": {},
        },

        "remote_components": {
            "ejs:npm",
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


def get_video_info(url: str) -> dict[str, Any]:

    validate_youtube_url(url)

    options = _base_ydl_options()

    options.update(
        {
            "skip_download": True,
        }
    )

    try:

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

    except DownloadError as exc:

        raise DownloadFailedError(
            str(exc)
        ) from exc

    if info is None:

        raise DownloadFailedError(
            "No se pudo obtener información del video."
        )

    from palette import (
        attach_palette,
        best_thumbnail_url,
    )

    return attach_palette(
        {
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "thumbnail": best_thumbnail_url(info),
            "webpage_url": info.get(
                "webpage_url",
                url,
            ),
        }
    )


def _build_ydl_options(
    output_template: str,
    audio_format: str,
    embed_thumbnail: bool,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:

    options = _base_ydl_options()

    options["outtmpl"] = output_template

    if progress_callback:

        options["progress_hooks"] = [
            progress_callback
        ]

    postprocessors: list[dict[str, Any]] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "192",
        }
    ]

    if embed_thumbnail:

        options["writethumbnail"] = True

        postprocessors.append(
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            }
        )

        postprocessors.append(
            {
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            }
        )

    options["postprocessors"] = postprocessors

    return options


def _run_yt_dlp(
    output_template: str,
    url: str,
    audio_format: str,
    embed_thumbnail: bool,
    progress_callback: ProgressCallback | None = None,
):

    options = _build_ydl_options(
        output_template=output_template,
        audio_format=audio_format,
        embed_thumbnail=embed_thumbnail,
        progress_callback=progress_callback,
    )

    with yt_dlp.YoutubeDL(options) as ydl:

        return ydl.extract_info(
            url,
            download=True,
        )


def download_audio(
    url: str,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, str]:

    validate_youtube_url(url)

    audio_format = audio_format.lower()

    if audio_format not in SUPPORTED_FORMATS:

        raise ValueError(
            f"Formato no soportado: {audio_format}. "
            f"Usa uno de: "
            f"{', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    _ensure_ffmpeg_available()

    embed_thumbnail = (
        audio_format in THUMBNAIL_EMBED_FORMATS
    )

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="yt-audio-"
        )
    )

    output_template = str(
        temp_dir / "%(title)s.%(ext)s"
    )

    try:

        info = _run_yt_dlp(
            output_template=output_template,
            url=url,
            audio_format=audio_format,
            embed_thumbnail=embed_thumbnail,
            progress_callback=progress_callback,
        )

    except DownloadError as exc:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        message = str(exc)

        if "403" in message:

            raise DownloadFailedError(
                "YouTube rechazó la descarga con HTTP 403. "
                "El video requiere una autenticación o "
                "PO Token que yt-dlp no pudo obtener."
            ) from exc

        if "LOGIN_REQUIRED" in message:

            raise DownloadFailedError(
                "YouTube requiere iniciar sesión para "
                "este video."
            ) from exc

        raise DownloadFailedError(
            message
        ) from exc

    except Exception as exc:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        raise DownloadFailedError(
            str(exc)
        ) from exc

    if info is None:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        raise DownloadFailedError(
            "No se pudo descargar el audio."
        )

    title = (
        info.get("title")
        or "audio"
    )

    downloaded_files = list(
        temp_dir.glob(
            f"*.{audio_format}"
        )
    )

    if not downloaded_files:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        raise DownloadFailedError(
            "La descarga terminó pero "
            "no se encontró el archivo de audio."
        )

    return downloaded_files[0], title
