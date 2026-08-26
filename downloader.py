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


# =========================================================
# YOUTUBE URL
# =========================================================

def validate_youtube_url(url: str) -> str:
    """
    Valida que la URL proporcionada pertenezca a YouTube.
    """

    if not isinstance(url, str):
        raise InvalidYouTubeURLError(
            "La URL debe ser un texto válido."
        )

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


# =========================================================
# FFMPEG
# =========================================================

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


# =========================================================
# COOKIES
# =========================================================

def _get_cookie_file() -> str | None:
    """
    Busca un archivo de cookies opcional.

    Las cookies NO son obligatorias para el funcionamiento
    normal del proveedor PO Token.

    Se mantienen como mecanismo de respaldo para casos en
    los que YouTube solicite autenticación adicional.

    Orden:

    1. YTDLP_COOKIES_FILE
    2. /etc/secrets/<nombre>
    3. YTDLP_COOKIES_B64
    4. YTDLP_COOKIES
    5. /app/cookies.txt
    6. /etc/secrets/cookies.txt
    7. cookies.txt junto a este archivo
    """

    env_path = os.environ.get(
        "YTDLP_COOKIES_FILE"
    )

    if env_path:
        path = Path(env_path)

        if path.is_file():
            return str(path)

        secrets_path = (
            Path("/etc/secrets") / path.name
        )

        if secrets_path.is_file():
            return str(secrets_path)

    # -----------------------------------------------------
    # Base64
    # -----------------------------------------------------

    b64 = os.environ.get(
        "YTDLP_COOKIES_B64"
    )

    if b64:
        try:
            data = base64.b64decode(
                b64,
                validate=True,
            )
        except Exception:
            data = None

        if data:
            tmp = (
                Path(tempfile.gettempdir())
                / f"ytdlp_cookies_{uuid.uuid4().hex}.txt"
            )

            try:
                tmp.write_bytes(data)
                return str(tmp)
            except Exception:
                pass

    # -----------------------------------------------------
    # Raw cookies
    # -----------------------------------------------------

    raw = os.environ.get(
        "YTDLP_COOKIES"
    )

    if raw:
        tmp = (
            Path(tempfile.gettempdir())
            / f"ytdlp_cookies_{uuid.uuid4().hex}.txt"
        )

        try:
            tmp.write_text(
                raw,
                encoding="utf-8",
            )
            return str(tmp)
        except Exception:
            pass

    # -----------------------------------------------------
    # Docker
    # -----------------------------------------------------

    default_path = Path(
        "/app/cookies.txt"
    )

    if default_path.is_file():
        return str(default_path)

    # -----------------------------------------------------
    # Render secret
    # -----------------------------------------------------

    etc_secret = Path(
        "/etc/secrets/cookies.txt"
    )

    if etc_secret.is_file():
        return str(etc_secret)

    # -----------------------------------------------------
    # Archivo local
    # -----------------------------------------------------

    local_path = (
        Path(__file__).resolve().parent
        / "cookies.txt"
    )

    if local_path.is_file():
        return str(local_path)

    return None


# =========================================================
# YT-DLP
# =========================================================

def _base_ydl_options() -> dict[str, Any]:
    """
    Configuración central de yt-dlp.

    La parte importante de esta configuración es:

        youtubepot-bgutilhttp

    que permite al plugin bgutil solicitar automáticamente
    PO Tokens al servidor local:

        http://127.0.0.1:4416

    Esto elimina la necesidad de copiar manualmente un
    PO Token para cada vídeo.
    """

    options: dict[str, Any] = {
        # -------------------------------------------------
        # General
        # -------------------------------------------------

        "quiet": False,

        "no_warnings": False,

        "noprogress": False,

        # -------------------------------------------------
        # Formato
        # -------------------------------------------------

        "format": (
            "bestaudio[ext=m4a]/"
            "bestaudio[ext=webm]/"
            "bestaudio[ext=mp4]/"
            "bestaudio/"
            "best"
        ),

        # -------------------------------------------------
        # Reintentos
        # -------------------------------------------------

        "retries": 10,

        "fragment_retries": 10,

        "file_access_retries": 5,

        # -------------------------------------------------
        # Red
        # -------------------------------------------------

        "force_ipv4": True,

        "socket_timeout": 90,

        "connect_timeout": 90,

        "read_timeout": 90,

        "http_chunk_size": 10485760,

        # -------------------------------------------------
        # JavaScript / Deno
        # -------------------------------------------------

        "js_runtimes": {
            "deno": {
                "path": "deno",
            }
        },

        # -------------------------------------------------
        # Componentes EJS
        # -------------------------------------------------

        "remote_components": {
            "ejs": "github",
        },

        # -------------------------------------------------
        # YOUTUBE
        # -------------------------------------------------
        #
        # mweb es el cliente recomendado por la guía actual
        # de yt-dlp cuando se utiliza un proveedor PO Token.
        #
        # bgutil proporciona automáticamente el token.
        # -------------------------------------------------

        "extractor_args": {
            "youtube": {
                "player_client": [
                    "mweb"
                ],
            },

            "youtubepot-bgutilhttp": {
                "base_url": (
                    "http://127.0.0.1:4416"
                ),
            },
        },

        # -------------------------------------------------
        # User-Agent
        # -------------------------------------------------

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/139.0.0.0 "
                "Safari/537.36"
            ),

            "Accept-Language": (
                "es-CO,es;q=0.9,en;q=0.8"
            ),

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),

            "Accept-Encoding": (
                "gzip, deflate, br"
            ),

            "DNT": "1",

            "Connection": "keep-alive",

            "Upgrade-Insecure-Requests": "1",

            "Sec-Fetch-Dest": "document",

            "Sec-Fetch-Mode": "navigate",

            "Sec-Fetch-Site": "none",

            "Sec-Fetch-User": "?1",

            "Sec-Ch-Ua": (
                '"Chromium";v="139", '
                '"Not;A=Brand";v="99"'
            ),

            "Sec-Ch-Ua-Mobile": "?0",

            "Sec-Ch-Ua-Platform": (
                '"Windows"'
            ),
        },

        # -------------------------------------------------
        # SSL / HTTP
        # -------------------------------------------------

        "suppress_http_warnings": True,

        "no_check_certificate": True,

        # -------------------------------------------------
        # Geolocalización
        # -------------------------------------------------

        "geo_bypass": True,

        # -------------------------------------------------
        # Fragmentos
        # -------------------------------------------------

        "skip_unavailable_fragments": True,

        # -------------------------------------------------
        # FFmpeg
        # -------------------------------------------------

        "prefer_ffmpeg": True,

        # -------------------------------------------------
        # Formatos
        # -------------------------------------------------

        "allow_unplayable_formats": False,
    }

    # =====================================================
    # PROXY OPCIONAL
    # =====================================================

    proxy = os.environ.get(
        "YTDLP_PROXY"
    )

    if proxy:
        options["proxy"] = proxy

    # =====================================================
    # COOKIES OPCIONALES
    # =====================================================

    cookies_file = _get_cookie_file()

    if cookies_file:
        print(
            "[yt-dlp] Usando archivo de cookies "
            f"opcional: {cookies_file}"
        )

        options["cookiefile"] = cookies_file

    else:
        print(
            "[yt-dlp] No se encontró cookies.txt. "
            "Se utilizará PO Token Provider."
        )

    return options


# =========================================================
# INFORMACIÓN DEL VIDEO
# =========================================================

def get_video_info(
    url: str,
) -> dict[str, Any]:
    """
    Obtiene información básica de un vídeo de YouTube.
    """

    validate_youtube_url(url)

    options = _base_ydl_options()

    options["skip_download"] = True

    options["noplaylist"] = True

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

        raise DownloadFailedError(
            _friendly_download_error(
                message
            )
        ) from exc

    except Exception as exc:
        raise DownloadFailedError(
            str(exc)
        ) from exc

    if info is None:
        raise DownloadFailedError(
            "No se pudo obtener información "
            "del video."
        )

    # =====================================================
    # PALETA
    # =====================================================

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


# =========================================================
# OPCIONES DE DESCARGA
# =========================================================

def _build_ydl_options(
    output_template: str,
    audio_format: str,
    embed_thumbnail: bool,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """
    Construye las opciones finales de yt-dlp.
    """

    options = _base_ydl_options()

    options["outtmpl"] = output_template

    options["noplaylist"] = True

    if progress_callback:
        options["progress_hooks"] = [
            progress_callback
        ]

    # =====================================================
    # POSTPROCESADORES
    # =====================================================

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

    # =====================================================
    # MINIATURA
    # =====================================================

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


# =========================================================
# EJECUTAR YT-DLP
# =========================================================

def _run_yt_dlp(
    output_template: str,
    url: str,
    audio_format: str,
    embed_thumbnail: bool,
    progress_callback: ProgressCallback | None = None,
):
    """
    Ejecuta yt-dlp utilizando la configuración central.
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


# =========================================================
# MENSAJES DE ERROR
# =========================================================

def _friendly_download_error(
    message: str,
) -> str:
    """
    Convierte errores técnicos de yt-dlp en mensajes
    más útiles para la API.
    """

    lowered = message.lower()

    # -----------------------------------------------------
    # PO TOKEN / BOT
    # -----------------------------------------------------

    if (
        "failed to extract any player response"
        in lowered
    ):
        return (
            "YouTube no devolvió una respuesta válida "
            "del reproductor. El proveedor PO Token "
            "puede estar iniciándose o YouTube puede "
            "haber cambiado temporalmente su sistema. "
            "Intenta nuevamente."
        )

    if (
        "sign in to confirm"
        in lowered
        or "not a bot"
        in lowered
        or "po token"
        in lowered
    ):
        return (
            "YouTube está solicitando una verificación "
            "adicional. El proveedor PO Token no pudo "
            "completarla para este vídeo. Intenta "
            "nuevamente más tarde."
        )

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    if (
        "login_required"
        in lowered
        or "please sign in"
        in lowered
        or "authentication required"
        in lowered
    ):
        return (
            "YouTube requiere autenticación para este "
            "vídeo. Si es un contenido privado o "
            "restringido, puede ser necesario proporcionar "
            "cookies válidas."
        )

    # -----------------------------------------------------
    # 403
    # -----------------------------------------------------

    if (
        "http error 403"
        in lowered
        or "403 forbidden"
        in lowered
    ):
        return (
            "YouTube rechazó la solicitud con HTTP 403. "
            "El vídeo o la IP pueden estar temporalmente "
            "restringidos."
        )

    # -----------------------------------------------------
    # 429
    # -----------------------------------------------------

    if (
        "http error 429"
        in lowered
        or "too many requests"
        in lowered
    ):
        return (
            "YouTube limitó temporalmente la cantidad de "
            "solicitudes desde esta IP. Intenta nuevamente "
            "más tarde."
        )

    # -----------------------------------------------------
    # FORMATO
    # -----------------------------------------------------

    if (
        "requested format is not available"
        in lowered
    ):
        return (
            "El formato de audio solicitado no está "
            "disponible para este vídeo. Puede tratarse "
            "de un livestream, vídeo privado o contenido "
            "con restricciones."
        )

    # -----------------------------------------------------
    # VIDEO NO DISPONIBLE
    # -----------------------------------------------------

    if (
        "video unavailable"
        in lowered
        or "this video is unavailable"
        in lowered
    ):
        return (
            "El vídeo no está disponible en YouTube."
        )

    # -----------------------------------------------------
    # GEO
    # -----------------------------------------------------

    if (
        "not available in your country"
        in lowered
        or "geo-restricted"
        in lowered
    ):
        return (
            "Este vídeo tiene restricciones "
            "geográficas."
        )

    # -----------------------------------------------------
    # ERROR GENÉRICO
    # -----------------------------------------------------

    if (
        "unable to extract"
        in lowered
    ):
        return (
            "No se pudo extraer la información del "
            "vídeo. YouTube puede haber cambiado "
            "temporalmente su sistema de reproducción."
        )

    return message


# =========================================================
# DESCARGAR AUDIO
# =========================================================

def download_audio(
    url: str,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, str, str]:
    """
    Descarga un vídeo de YouTube y lo convierte al formato
    de audio solicitado.

    Retorna:

        (archivo, título, uploader)
    """

    validate_youtube_url(url)

    audio_format = audio_format.lower().strip()

    # =====================================================
    # VALIDAR FORMATO
    # =====================================================

    if audio_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Formato no soportado: "
            f"{audio_format}. "
            f"Usa uno de: "
            f"{', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    # =====================================================
    # FFMPEG
    # =====================================================

    _ensure_ffmpeg_available()

    # =====================================================
    # MINIATURA
    # =====================================================

    embed_thumbnail = (
        audio_format
        in THUMBNAIL_EMBED_FORMATS
    )

    # =====================================================
    # DIRECTORIO TEMPORAL
    # =====================================================

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

        raise DownloadFailedError(
            _friendly_download_error(
                message
            )
        ) from exc

    except Exception as exc:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        raise DownloadFailedError(
            str(exc)
        ) from exc

    # =====================================================
    # VALIDAR INFO
    # =====================================================

    if info is None:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        raise DownloadFailedError(
            "No se pudo descargar el audio."
        )

    # =====================================================
    # METADATA
    # =====================================================

    title = (
        info.get("title")
        or "audio"
    )

    uploader = (
        info.get("uploader")
        or info.get("channel")
        or ""
    )

    # =====================================================
    # BUSCAR ARCHIVO
    # =====================================================

    downloaded_files = list(
        temp_dir.glob(
            f"*.{audio_format}"
        )
    )

    # =====================================================
    # SI NO ENCUENTRA ARCHIVO
    # =====================================================

    if not downloaded_files:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        # En algunos casos FFmpeg puede producir una
        # extensión distinta. Buscamos cualquier archivo
        # de audio antes de declarar el proceso fallido.

        possible_audio_files = []

        for extension in (
            "mp3",
            "m4a",
            "opus",
            "wav",
        ):
            possible_audio_files.extend(
                temp_dir.glob(
                    f"*.{extension}"
                )
            )

        if possible_audio_files:
            return (
                possible_audio_files[0],
                title,
                uploader,
            )

        raise DownloadFailedError(
            "La descarga terminó pero no se encontró "
            "el archivo de audio."
        )

    # =====================================================
    # RESULTADO
    # =====================================================

    return (
        downloaded_files[0],
        title,
        uploader,
    )
