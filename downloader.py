from __future__ import annotations

from collections.abc import Callable
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
import base64
import uuid

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


def _ensure_ffmpeg_available() -> None:

    if shutil.which("ffmpeg") is not None:
        return

    possible_paths = (
        "/usr/bin",
        "/usr/local/bin",
        "/opt/homebrew/bin",
    )

    for directory in possible_paths:

        ffmpeg_path = Path(directory) / "ffmpeg"

        if ffmpeg_path.exists():

            os.environ["PATH"] = (
                f"{directory}:"
                f"{os.environ.get('PATH', '')}"
            )

            return

    raise DownloadFailedError(
        "ffmpeg no está instalado."
    )


def _get_cookie_file() -> str | None:
    """
    Look for cookies to pass to yt-dlp. Order of precedence:
    1. YTDLP_COOKIES_FILE environment variable (path to a cookies.txt file)
    2. YTDLP_COOKIES_B64 environment variable (base64-encoded cookies file contents)
    3. YTDLP_COOKIES environment variable (raw cookies file contents)
    4. /app/cookies.txt (useful in Docker)
    5. cookies.txt alongside this module

    If cookies are supplied via environment (B64 or raw), this function will
    write them to a temporary file and return its path.
    """

    env_path = os.environ.get(
        "YTDLP_COOKIES_FILE"
    )

    if env_path:

        path = Path(env_path)

        if path.is_file():
            return str(path)

    # Support base64-encoded cookies in an env var (useful for CI / Docker secrets)
    b64 = os.environ.get("YTDLP_COOKIES_B64")

    if b64:
        try:
            data = base64.b64decode(b64)
        except Exception:
            # If decoding fails, fall through and try other sources
            data = None

        if data:
            tmp = Path(tempfile.gettempdir()) / f"ytdlp_cookies_{uuid.uuid4().hex}.txt"
            try:
                tmp.write_bytes(data)
                return str(tmp)
            except Exception:
                pass

    # Support raw cookies content in an env var
    raw = os.environ.get("YTDLP_COOKIES")

    if raw:
        tmp = Path(tempfile.gettempdir()) / f"ytdlp_cookies_{uuid.uuid4().hex}.txt"
        try:
            tmp.write_text(raw)
            return str(tmp)
        except Exception:
            pass

    default_path = Path(
        "/app/cookies.txt"
    )

    if default_path.is_file():
        return str(default_path)

    local_path = (
        Path(__file__).resolve().parent
        / "cookies.txt"
    )

    if local_path.is_file():
        return str(local_path)

    return None


def _base_ydl_options() -> dict[str, Any]:

    options: dict[str, Any] = {

        "quiet": True,

        "no_warnings": True,

        # Formato flexible que acepta cualquier audio disponible
        "format": (
            "bestaudio[ext=m4a]/"
            "bestaudio[ext=webm]/"
            "bestaudio[ext=mp4]/"
            "bestaudio/"
            "best"
        ),

        "retries": 10,

        "fragment_retries": 10,

        "force_ipv4": True,

        "socket_timeout": 30,

        "connect_timeout": 30,

        "read_timeout": 30,

        "js_runtimes": {
            "deno": {},
        },

        "remote_components": {
            "ejs:npm",
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 "
                "Safari/537.36"
            ),

            "Accept-Language": (
                "en-US,en;q=0.9"
            ),

            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),

            "Accept-Encoding": (
                "gzip, deflate"
            ),

            "DNT": "1",

            "Connection": "keep-alive",

            "Upgrade-Insecure-Requests": "1",
        },

        "extractor_args": {
            "youtube": {
                "player_client": ["web", "mweb", "android"],
                "player_skip": ["js", "webpage"],
                "skip": ["hls", "dash"],
            }
        },

        "suppress_http_warnings": True,

        "no_check_certificate": True,

        "geo_bypass": True,

        "geo_bypass_country": "US",
    }

    # Proxy support (useful if your server IP is geo-blocked)
    proxy = os.environ.get("YTDLP_PROXY")
    if proxy:
        options["proxy"] = proxy

    cookies_file = _get_cookie_file()

    if cookies_file:
        options["cookiefile"] = cookies_file

    return options


def _try_cookies_from_browser(url: str, base_options: dict[str, Any], download: bool) -> dict[str, Any] | None:
    """Attempt to let yt-dlp read cookies directly from local browsers.

    This tries a list of common browser names supported by yt-dlp's
    --cookies-from-browser feature. It returns the info dict if successful,
    or None if all attempts fail.
    """
    # Browsers to try (order matters: chrome/chromium first)
    browsers = os.environ.get("YTDLP_COOKIES_FROM_BROWSER", "chrome,chromium,firefox,edge,safari").split(",")

    for browser in browsers:
        browser = browser.strip()
        if not browser:
            continue

        opts = dict(base_options)
        # Use the yt-dlp option name for cookies-from-browser
        opts["cookiesfrombrowser"] = browser

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    url,
                    download=download,
                )

                # If we get an info dict, consider the attempt successful
                if info is not None:
                    print(f"INFO: used cookies from browser '{browser}'")
                    return info

        except DownloadError as exc:
            message = str(exc)
            # If the failure is related to login, try the next browser
            if (
                "Sign in to confirm" in message
                or "LOGIN_REQUIRED" in message
            ):
                print(f"WARN: browser '{browser}' did not provide valid cookies (LOGIN_REQUIRED)")
                continue

            # For other errors, re-raise so we don't mask issues
            raise

        except Exception:
            # If any unexpected error occurs while trying a browser, continue
            continue

    return None


def get_video_info(
    url: str,
) -> dict[str, Any]:

    validate_youtube_url(url)

    options = _base_ydl_options()

    options["skip_download"] = True

    try:

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

    except DownloadError as exc:
        message = str(exc)

        # If the error indicates login is required, try reading cookies from browser
        if (
            "Sign in to confirm" in message
            or "LOGIN_REQUIRED" in message
        ):
            try:
                fallback = _try_cookies_from_browser(url, options, download=False)
                if fallback is not None:
                    info = fallback
                else:
                    raise DownloadFailedError(
                        "YouTube está bloqueando esta solicitud. Las cookies no son válidas o la sesión requiere autenticación. Proporciona cookies (YTDLP_COOKIES_B64/YTDLP_COOKIES or YTDLP_COOKIES_FILE)."
                    ) from exc
            except DownloadError as exc2:
                raise DownloadFailedError(str(exc2)) from exc2

        else:
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

            "duration": info.get(
                "duration"
            ),

            "uploader": info.get(
                "uploader"
            ),

            "thumbnail": best_thumbnail_url(
                info
            ),

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

    postprocessors: list[
        dict[str, Any]
    ] = [
        {
            "key": "FFmpegExtractAudio",

            "preferredcodec": audio_format,

            "preferredquality": "192",

            "nopostoverwrites": False,
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

    options["postprocessors"] = (
        postprocessors
    )

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

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        return ydl.extract_info(
            url,
            download=True,
        )


def download_audio(
    url: str,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, str, str]:

    validate_youtube_url(url)

    audio_format = audio_format.lower()

    if audio_format not in SUPPORTED_FORMATS:

        raise ValueError(
            f"Formato no soportado: "
            f"{audio_format}. "
            f"Usa uno de: "
            f"{', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    _ensure_ffmpeg_available()

    embed_thumbnail = (
        audio_format
        in THUMBNAIL_EMBED_FORMATS
    )

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="yt-audio-"
        )
    )

    output_template = str(
        temp_dir
        / "%(title)s.%(ext)s"
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

        # If login required, try to read cookies directly from browsers installed on host
        if (
            "Sign in to confirm" in message
            or "LOGIN_REQUIRED" in message
        ):
            try:
                # Build base options to reuse when trying cookies-from-browser
                base_opts = _build_ydl_options(
                    output_template=output_template,
                    audio_format=audio_format,
                    embed_thumbnail=embed_thumbnail,
                    progress_callback=progress_callback,
                )

                fallback = _try_cookies_from_browser(url, base_opts, download=True)

                if fallback is None:
                    raise DownloadFailedError(
                        "YouTube está bloqueando esta solicitud. Las cookies de YouTube no son válidas o la sesión requiere autenticación. Proporciona cookies mediante YTDLP_COOKIES_B64/YTDLP_COOKIES/YTDLP_COOKIES_FILE o monta /app/cookies.txt."
                    ) from exc

                info = fallback

            except DownloadError as exc2:
                raise DownloadFailedError(str(exc2)) from exc2

        else:
            if "HTTP Error 403" in message:

                raise DownloadFailedError(
                    "YouTube rechazó la descarga con HTTP 403. Intenta más tarde o verifica tu conexión."
                ) from exc

            if "Requested format is not available" in message:

                raise DownloadFailedError(
                    "El formato de audio no está disponible para este video. Es posible que sea un livestream, video privado o esté restringido geográficamente."
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

    uploader = (
        info.get("uploader")
        or info.get("channel")
        or ""
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
            "La descarga terminó pero no se encontró el archivo de audio."
        )

    return (
        downloaded_files[0],
        title,
        uploader,
    )
