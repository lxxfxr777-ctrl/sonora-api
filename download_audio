from __future__ import annotations

from collections.abc import Callable
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError


YOUTUBE_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|music\.youtube\.com/watch\?v=)[\w-]+"
)

SUPPORTED_FORMATS = {"mp3", "m4a", "opus", "wav"}

THUMBNAIL_EMBED_FORMATS = {"mp3", "m4a", "opus"}

ProgressCallback = Callable[[dict[str, Any]], None]


class InvalidYouTubeURLError(ValueError):
    pass


class DownloadFailedError(RuntimeError):
    pass


_WRITABLE_COOKIES_PATH = Path(tempfile.gettempdir()) / "sonora_cookies.txt"


def _get_cookies_file() -> str | None:
    source_path: Path | None = None

    env_path = os.environ.get("YTDLP_COOKIES_FILE")
    if env_path and Path(env_path).is_file():
        source_path = Path(env_path)

    if source_path is None:
        local_path = Path(__file__).resolve().parent.parent / "cookies.txt"
        if local_path.is_file():
            source_path = local_path

    if source_path is None:
        return None

    try:
        shutil.copyfile(source_path, _WRITABLE_COOKIES_PATH)
    except OSError:
        return None

    return str(_WRITABLE_COOKIES_PATH)


def _ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is not None:
        return

    for brew_bin in ("/opt/homebrew/bin", "/usr/local/bin"):
        ffmpeg_path = Path(brew_bin) / "ffmpeg"
        if ffmpeg_path.exists():
            os.environ["PATH"] = f"{brew_bin}:{os.environ.get('PATH', '')}"
            return

    raise DownloadFailedError(
        "ffmpeg no está instalado. En Windows: winget install Gyan.FFmpeg "
        "(o choco install ffmpeg). En macOS: brew install ffmpeg."
    )


def validate_youtube_url(url: str) -> str:
    url = url.strip()

    if not url:
        raise InvalidYouTubeURLError("La URL no puede estar vacía.")

    if not YOUTUBE_URL_PATTERN.match(url):
        raise InvalidYouTubeURLError(
            "La URL no parece ser un enlace válido de YouTube."
        )

    return url


def get_video_info(url: str) -> dict[str, Any]:
    validate_youtube_url(url)

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best/251/140",
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android", "ios"]
            }
        },
    }

    cookies_file = _get_cookies_file()

    if cookies_file:
        options["cookiefile"] = cookies_file

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

    except DownloadError as exc:
        raise DownloadFailedError(str(exc)) from exc

    if info is None:
        raise DownloadFailedError(
            "No se pudo obtener información del video."
        )

    from palette import attach_palette, best_thumbnail_url

    return attach_palette(
        {
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "thumbnail": best_thumbnail_url(info),
            "webpage_url": info.get("webpage_url", url),
        }
    )


def _build_ydl_options(
    output_template: str,
    audio_format: str,
    embed_thumbnail: bool,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:

    postprocessors: list[dict[str, Any]] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "192",
        }
    ]

    options: dict[str, Any] = {
        "format": "bestaudio/best/251/140",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android", "ios"]
            }
        },
        "progress_hooks": (
            [progress_callback]
            if progress_callback
            else []
        ),
    }

    cookies_file = _get_cookies_file()

    if cookies_file:
        options["cookiefile"] = cookies_file

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
) -> dict[str, Any] | None:

    options = _build_ydl_options(
        output_template,
        audio_format,
        embed_thumbnail,
        progress_callback,
    )

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=True)


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
            f"Usa uno de: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    _ensure_ffmpeg_available()

    embed_thumbnail = audio_format in THUMBNAIL_EMBED_FORMATS

    temp_dir = Path(
        tempfile.mkdtemp(prefix="yt-audio-")
    )

    output_template = str(
        temp_dir / "%(title)s.%(ext)s"
    )

    try:

        info = _run_yt_dlp(
            output_template,
            url,
            audio_format,
            embed_thumbnail,
            progress_callback,
        )

    except DownloadError as exc:

        if embed_thumbnail:

            shutil.rmtree(
                temp_dir,
                ignore_errors=True,
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
                    output_template,
                    url,
                    audio_format,
                    False,
                    progress_callback,
                )

            except DownloadError as exc_retry:

                shutil.rmtree(
                    temp_dir,
                    ignore_errors=True,
                )

                raise DownloadFailedError(
                    str(exc_retry)
                ) from exc_retry

        else:

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

    title = info.get("title") or "audio"

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
            "La descarga terminó pero no se encontró "
            "el archivo de audio."
        )

    return downloaded_files[0], title
