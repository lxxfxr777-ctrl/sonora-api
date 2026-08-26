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


def _get_node_path() -> str:
    """
    Obtiene la ruta de Node.js.

    El Dockerfile de SONORA instala Node.js 25.
    yt-dlp necesita que Node se habilite explícitamente
    para ejecutar los solucionadores EJS de YouTube.
    """

    node_path = shutil.which("node")

    if node_path is None:
        raise DownloadFailedError(
            "Node.js no está disponible en el contenedor."
        )

    return node_path


def validate_youtube_url(url: str) -> str:
    """
    Valida que la URL corresponda a YouTube.
    """

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
    """
    Comprueba que FFmpeg esté disponible.
    """

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
    Devuelve el archivo de cookies que debe usar yt-dlp, si existe.

    Prioridad:
    1. YTDLP_COOKIES_FILE, si apunta a un archivo existente.
    2. /app/cookies.txt, que es el archivo usado por los endpoints de la API.

    No se cargan cookies si el archivo no existe.
    """
    configured = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    candidates = [configured] if configured else []
    candidates.append("/app/cookies.txt")

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate

    return None


def _base_ydl_options() -> dict[str, Any]:
    """
    Opciones centrales de yt-dlp para SONORA.

    IMPORTANTE:

    - Utiliza cookies solo si se proporciona un archivo válido.
    - No actualiza yt-dlp durante cada petición.
    - Utiliza Node.js para EJS.
    - Habilita ejs:github.
    - Utiliza bgutil HTTP en 127.0.0.1:4416.
    """

    node_path = _get_node_path()

    options: dict[str, Any] = {
        # =================================================
        # SALIDA
        # =================================================

        "quiet": False,
        "no_warnings": False,

        # =================================================
        # FORMATO
        # =================================================

        "format": (
            "bestaudio[ext=m4a]/"
            "bestaudio[ext=webm]/"
            "bestaudio[ext=mp4]/"
            "bestaudio/"
            "best"
        ),

        # =================================================
        # REINTENTOS
        # =================================================

        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,

        # =================================================
        # RED
        # =================================================

        "force_ipv4": True,

        "socket_timeout": 60,
        "connect_timeout": 60,
        "read_timeout": 60,

        "http_chunk_size": 10485760,

        # =================================================
        # JAVASCRIPT / EJS
        # =================================================
        #
        # YouTube necesita un runtime JS para los desafíos
        # actuales.
        #
        # El Dockerfile de SONORA proporciona Node.js.
        #
        # =================================================

        "js_runtimes": {
            "node": {
                "path": node_path,
            },
        },

        # Permitir que yt-dlp obtenga los scripts EJS
        # directamente desde el repositorio oficial.
        "remote_components": {
            "ejs:github",
        },

        # =================================================
        # YOUTUBE + BGUTIL
        # =================================================
        #
        # mweb es el cliente recomendado para este flujo.
        #
        # bgutil está ejecutándose dentro del mismo
        # contenedor en:
        #
        # http://127.0.0.1:4416
        #
        # =================================================

        "extractor_args": {
            "youtube": {
                "player_client": [
                    "mweb",
                ],
            },

            "youtubepot-bgutilhttp": {
                "base_url": [
                    "http://127.0.0.1:4416",
                ],
            },
        },

        # =================================================
        # HEADERS
        # =================================================

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/142.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7",
        },

        # =================================================
        # SEGURIDAD / CONEXIÓN
        # =================================================

        "suppress_http_warnings": True,

        "no_check_certificate": True,

        # =================================================
        # GEO
        # =================================================

        "geo_bypass": True,

        "geo_bypass_country": "CO",

        # =================================================
        # FRAGMENTOS
        # =================================================

        "skip_unavailable_fragments": True,

        # =================================================
        # FFMPEG
        # =================================================

        "prefer_ffmpeg": True,

        # =================================================
        # FORMATOS
        # =================================================

        "allow_unplayable_formats": False,

        # Evita que una URL de playlist haga múltiples descargas
        # cuando la API espera un solo vídeo.
        "noplaylist": True,

        # Mantiene una caché local para EJS/yt-dlp.
        "cachedir": "/tmp/yt-dlp-cache",
    }

    # =====================================================
    # COOKIES OPCIONALES
    # =====================================================

    cookie_file = _get_cookie_file()
    if cookie_file:
        options["cookiefile"] = cookie_file

    # =====================================================
    # PROXY OPCIONAL
    # =====================================================

    proxy = os.environ.get(
        "YTDLP_PROXY"
    )

    if proxy:
        options["proxy"] = proxy

    return options


def get_video_info(
    url: str,
) -> dict[str, Any]:
    """
    Obtiene información básica de un vídeo de YouTube.
    """

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

        if "Failed to extract any player response" in message:
            raise DownloadFailedError(
                "YouTube no devolvió una respuesta válida "
                "del reproductor. El solucionador EJS o "
                "el proveedor PO Token no pudo completar "
                "la solicitud."
            ) from exc

        if (
            "Sign in to confirm" in message
            or "LOGIN_REQUIRED" in message
            or "Please sign in" in message
        ):
            raise DownloadFailedError(
                "YouTube está bloqueando esta solicitud "
                "por una comprobación de acceso o bot."
            ) from exc

        if "HTTP Error 403" in message:
            raise DownloadFailedError(
                "YouTube rechazó la solicitud con HTTP 403."
            ) from exc

        if "HTTP Error 429" in message:
            raise DownloadFailedError(
                "YouTube bloqueó temporalmente la IP "
                "por demasiadas solicitudes."
            ) from exc

        raise DownloadFailedError(
            message
        ) from exc

    except Exception as exc:

        raise DownloadFailedError(
            str(exc)
        ) from exc

    if info is None:
        raise DownloadFailedError(
            "No se pudo obtener información del vídeo."
        )

    from palette import (
        attach_palette,
        best_thumbnail_url,
    )

    return attach_palette(
        {
            "id": info.get("id"),

            "title": info.get(
                "title"
            ),

            "duration": info.get(
                "duration"
            ),

            "uploader": (
                info.get("uploader")
                or info.get("channel")
                or ""
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
    """
    Construye las opciones específicas para descargar
    y convertir el audio.
    """

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

            "preferredcodec": (
                audio_format
            ),

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
    """
    Ejecuta yt-dlp.
    """

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
    """
    Descarga el audio de YouTube y lo convierte
    al formato solicitado.
    """

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

        # =================================================
        # PLAYER RESPONSE
        # =================================================

        if (
            "Failed to extract any player response"
            in message
        ):

            raise DownloadFailedError(
                "YouTube no devolvió una respuesta "
                "válida del reproductor. "
                "El solucionador EJS o el proveedor "
                "PO Token no pudo completar la solicitud."
            ) from exc

        # =================================================
        # BOT / LOGIN
        # =================================================

        if (
            "Sign in to confirm"
            in message
            or "LOGIN_REQUIRED"
            in message
            or "Please sign in"
            in message
        ):

            raise DownloadFailedError(
                "YouTube está bloqueando esta solicitud "
                "con una comprobación de bot o acceso."
            ) from exc

        # =================================================
        # HTTP 403
        # =================================================

        if "HTTP Error 403" in message:

            raise DownloadFailedError(
                "YouTube rechazó la descarga con HTTP 403."
            ) from exc

        # =================================================
        # HTTP 429
        # =================================================

        if "HTTP Error 429" in message:

            raise DownloadFailedError(
                "Demasiadas solicitudes. "
                "YouTube bloqueó temporalmente la IP."
            ) from exc

        # =================================================
        # FORMATO
        # =================================================

        if (
            "Requested format is not available"
            in message
        ):

            raise DownloadFailedError(
                "El formato de audio no está disponible "
                "para este vídeo."
            ) from exc

        # =================================================
        # OTROS ERRORES
        # =================================================

        if (
            "Unable to extract"
            in message
            or "ERROR"
            in message
        ):

            raise DownloadFailedError(
                "No se pudo extraer la información "
                "del vídeo. "
                f"Detalles: {message[:300]}"
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
            "La descarga terminó pero "
            "no se encontró el archivo de audio."
        )

    return (
        downloaded_files[0],
        title,
        uploader,
    )
