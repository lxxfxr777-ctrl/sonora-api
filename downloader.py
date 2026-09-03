from __future__ import annotations

import base64
import binascii
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yt_dlp

SUPPORTED_FORMATS = {"mp3", "m4a", "opus", "wav"}
COOKIE_PATH = Path(os.environ.get("YTDLP_COOKIES_FILE", "/app/cookies.txt"))


class InvalidYouTubeURLError(ValueError):
    pass


class DownloadFailedError(RuntimeError):
    pass


def _install_env_cookies() -> str | None:
    """Materialize a Netscape cookies.txt stored in YTDLP_COOKIES_B64."""
    value = os.environ.get("YTDLP_COOKIES_B64", "").strip()
    if not value:
        return None

    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DownloadFailedError("YTDLP_COOKIES_B64 no contiene base64 válido.") from exc

    if not data.strip():
        raise DownloadFailedError("YTDLP_COOKIES_B64 está vacío.")

    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_PATH.write_bytes(data)
    try:
        os.chmod(COOKIE_PATH, 0o600)
    except OSError:
        pass
    return str(COOKIE_PATH)


def validate_youtube_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise InvalidYouTubeURLError("La URL no puede estar vacía.")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed_hosts = {
        "youtube.com", "www.youtube.com", "m.youtube.com",
        "music.youtube.com", "youtu.be",
    }
    if parsed.scheme not in {"http", "https"} or host not in allowed_hosts:
        raise InvalidYouTubeURLError("La URL no parece ser un enlace válido de YouTube.")
    return url


def _get_cookie_file() -> str | None:
    env_file = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    for candidate in (env_file, "/app/cookies.txt", "cookies.txt"):
        if candidate and Path(candidate).is_file() and Path(candidate).stat().st_size > 0:
            return candidate
    return None


def _base_ydl_options(player_clients: list[str] | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_args": {
            "youtube": {
                "player_client": player_clients or ["tv", "web_safari", "android"],
            }
        },
    }

    pot_url = os.environ.get("YTDLP_POT_PROVIDER_URL", "").strip()
    if pot_url and pot_url != "http://127.0.0.1:4416":
        opts["extractor_args"]["youtubepot-bgutilhttp"] = [f"base_url={pot_url}"]

    cookie_file = _get_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    return opts


def _extract_once(url: str, *, download: bool, player_clients: list[str], extra: dict[str, Any] | None) -> dict[str, Any]:
    opts = _base_ydl_options(player_clients)
    if extra:
        opts.update(extra)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=download)

    if not isinstance(info, dict):
        raise DownloadFailedError("YouTube no devolvió información válida del video.")
    return info


def _run_extract(url: str, download: bool = False, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_youtube_url(url)

    try:
        _install_env_cookies()
    except DownloadFailedError:
        raise

    strategies = [["tv"], ["web_safari"], ["android"], ["ios"]]
    errors: list[str] = []

    for clients in strategies:
        try:
            return _extract_once(url, download=download, player_clients=clients, extra=extra)
        except Exception as exc:
            errors.append(f"{'/'.join(clients)}: {exc}")

    detail = errors[-1] if errors else "Error desconocido."
    if not _get_cookie_file() and "Sign in to confirm you're not a bot" in detail:
        detail += " El servidor fue bloqueado por YouTube y no hay cookies configuradas."
    raise DownloadFailedError(detail)


def get_video_info(url: str) -> dict[str, Any]:
    try:
        info = _run_extract(url, download=False)
    except DownloadFailedError as exc:
        raise DownloadFailedError("No se pudo obtener la información del video: " + str(exc)) from exc

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


def download_audio(url: str, audio_format: str = "mp3", progress_callback: Any = None) -> tuple[Path, str, str]:
    validate_youtube_url(url)
    audio_format = audio_format.lower().strip()
    if audio_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Formato no soportado: {audio_format}. Usa uno de: {', '.join(sorted(SUPPORTED_FORMATS))}")

    temp_dir = Path(tempfile.mkdtemp(prefix="yt-audio-"))
    try:
        extra = {
            "format": "bestaudio/best",
            "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
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
            raise DownloadFailedError("La descarga terminó, pero no se encontró el archivo de audio.")

        output_file = files[0]
        if output_file.stat().st_size == 0:
            raise DownloadFailedError("Se generó un archivo de audio vacío.")

        if progress_callback:
            try:
                progress_callback({"status": "finished", "filename": str(output_file), "title": title, "uploader": uploader})
            except Exception:
                pass
        return output_file, title, uploader
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
