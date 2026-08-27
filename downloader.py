from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def _get_worker_url() -> str:
    worker_url = os.environ.get("WORKER_URL", "").strip()
    if not worker_url:
        raise DownloadFailedError("WORKER_URL no está configurada en Render.")

    worker_url = worker_url.rstrip("/")
    if not worker_url.startswith(("http://", "https://")):
        raise DownloadFailedError(
            "WORKER_URL debe comenzar con http:// o https://."
        )
    return worker_url


def _get_worker_token() -> str:
    return os.environ.get("WORKER_TOKEN", "").strip()


def _build_headers(content_type: str = "application/json") -> dict[str, str]:
    headers = {
        "Content-Type": content_type,
        "Accept": "application/json",
    }
    token = _get_worker_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _worker_request(
    endpoint: str,
    payload: dict[str, Any],
    timeout: int = 300,
) -> tuple[bytes, str]:
    worker_url = _get_worker_url()
    url = f"{worker_url.rstrip('/')}/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url=url,
        data=data,
        headers=_build_headers(),
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "") or ""
            return body, content_type
    except HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = str(exc)
        raise DownloadFailedError(
            f"Worker respondió HTTP {exc.code}: {error_body[:500]}"
        ) from exc
    except URLError as exc:
        raise DownloadFailedError(
            f"No se pudo conectar con el worker en {worker_url}. Detalles: {exc}"
        ) from exc
    except TimeoutError as exc:
        raise DownloadFailedError("El worker tardó demasiado en responder.") from exc
    except Exception as exc:
        raise DownloadFailedError(
            f"Error comunicándose con el worker: {exc}"
        ) from exc


def _decode_json_response(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise DownloadFailedError(
            "El worker devolvió una respuesta que no es JSON válido."
        ) from exc

    if not isinstance(data, dict):
        raise DownloadFailedError("El worker devolvió un JSON inválido.")
    return data


def _worker_info(url: str) -> dict[str, Any]:
    body, content_type = _worker_request(
        endpoint="/info",
        payload={"url": url},
        timeout=120,
    )

    if "application/json" not in content_type.lower():
        raise DownloadFailedError("El endpoint /info del worker no devolvió JSON.")

    data = _decode_json_response(body)
    if not data.get("ok"):
        raise DownloadFailedError(
            str(data.get("detail", "El worker no pudo obtener la información del vídeo."))
        )
    return data


def get_video_info(url: str) -> dict[str, Any]:
    validate_youtube_url(url)
    info = _worker_info(url)

    title = info.get("title") or "audio"
    uploader = info.get("uploader") or info.get("channel") or ""
    thumbnail = info.get("thumbnail")

    try:
        from palette import attach_palette, best_thumbnail_url

        normalized = {
            "id": info.get("id"),
            "title": title,
            "duration": info.get("duration"),
            "uploader": uploader,
            "thumbnail": best_thumbnail_url(info) if thumbnail else None,
            "webpage_url": info.get("webpage_url") or url,
        }
        return attach_palette(normalized)
    except Exception:
        return {
            "id": info.get("id"),
            "title": title,
            "duration": info.get("duration"),
            "uploader": uploader,
            "thumbnail": thumbnail,
            "webpage_url": info.get("webpage_url") or url,
        }


def download_audio(
    url: str,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, str, str]:
    validate_youtube_url(url)

    audio_format = audio_format.lower().strip()
    if audio_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Formato no soportado: {audio_format}. "
            f"Usa uno de: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    info = _worker_info(url)
    title = info.get("title") or "audio"
    uploader = info.get("uploader") or info.get("channel") or ""
    temp_dir = Path(tempfile.mkdtemp(prefix="yt-audio-worker-"))

    try:
        body, content_type = _worker_request(
            endpoint="/download",
            payload={"url": url, "format": audio_format},
            timeout=600,
        )

        if "application/json" in content_type.lower():
            try:
                error_data = _decode_json_response(body)
                detail = error_data.get(
                    "detail",
                    "El worker no pudo descargar el audio.",
                )
            except Exception:
                detail = body.decode("utf-8", errors="replace")[:500]
            raise DownloadFailedError(str(detail))

        output_file = temp_dir / f"audio.{audio_format}"
        output_file.write_bytes(body)

        if not output_file.exists():
            raise DownloadFailedError(
                "El worker respondió correctamente pero no se pudo guardar el audio."
            )

        if output_file.stat().st_size == 0:
            raise DownloadFailedError("El worker devolvió un archivo de audio vacío.")

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
        raise DownloadFailedError(str(exc)) from exc
