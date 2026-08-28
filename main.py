from __future__ import annotations

import asyncio
import net_ipv4  # noqa: F401  (debe importarse primero: fuerza DNS IPv4)

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse
import base64

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from downloader import (
    DownloadFailedError,
    InvalidYouTubeURLError,
    download_audio,
    get_video_info,
)


STATIC_DIR = Path(__file__).parent


app = FastAPI(
    title="YouTube Music API",
    description="API para descargar audio de videos de YouTube usando un enlace.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DownloadRequest(BaseModel):
    url: str = Field(
        ...,
        description="Enlace de YouTube (video o YouTube Music)",
    )

    format: str = Field(
        default="mp3",
        description="Formato de audio: mp3, m4a, opus, wav",
    )


def _is_api_key_valid(provided: str | None) -> bool:
    required = os.environ.get("YTDLP_COOKIES_API_KEY")
    if not required:
        return True
    if not provided:
        return False
    if provided.lower().startswith("bearer "):
        key = provided.split(None, 1)[1].strip()
        return key == required
    return provided == required


@app.get("/api")
def api_root() -> dict[str, str]:
    return {
        "message": "YouTube Music API",
        "docs": "/docs",
        "endpoints": "/api/info, /api/download, /api/cookies",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/info")
def video_info(
    url: str = Query(..., description="Enlace de YouTube"),
) -> dict:
    try:
        return get_video_info(url)
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DownloadFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/cover")
def cover_proxy(
    src: str = Query(..., description="URL de la portada"),
) -> Response:
    from palette import fetch_cover_bytes, is_allowed_cover_host
    parsed = urlparse(src)
    if parsed.scheme not in {"http", "https"} or not is_allowed_cover_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Portada no válida.")
    try:
        data, content_type = fetch_cover_bytes(src)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No se pudo cargar la portada.") from exc
    return Response(content=data, media_type=content_type)


# ---------------------------------------------------------------------------
# COOKIES TEMPORALES DE YOUTUBE
# ---------------------------------------------------------------------------
# Render no debe almacenar permanentemente las cookies de una cuenta.
# El archivo se guarda solamente en el contenedor actual y se elimina:
#   1) automáticamente después de YTDLP_COOKIES_TTL_SECONDS, o
#   2) cuando Render reinicia/reemplaza el contenedor.
#
# Por defecto: 6 horas. Se puede cambiar desde Render Environment.
COOKIES_DEST = Path(os.getenv("YTDLP_COOKIES_FILE", "/app/cookies.txt"))
COOKIES_TTL_SECONDS = max(300, int(os.getenv("YTDLP_COOKIES_TTL_SECONDS", "21600")))
_cookie_expiry_task: asyncio.Task | None = None


async def _expire_temporary_cookies(path: Path, uploaded_at: float) -> None:
    try:
        await asyncio.sleep(COOKIES_TTL_SECONDS)
        # No borres unas cookies nuevas si el usuario volvió a subirlas
        # antes de que venciera la carga anterior.
        try:
            if path.stat().st_mtime <= uploaded_at + 1:
                path.unlink(missing_ok=True)
                print("=== SONORA: temporary YouTube cookies expired ===", flush=True)
        except FileNotFoundError:
            pass
    except asyncio.CancelledError:
        pass


def _schedule_cookie_expiry(path: Path) -> None:
    global _cookie_expiry_task
    if _cookie_expiry_task and not _cookie_expiry_task.done():
        _cookie_expiry_task.cancel()
    uploaded_at = path.stat().st_mtime
    _cookie_expiry_task = asyncio.create_task(_expire_temporary_cookies(path, uploaded_at))


@app.post("/api/cookies/upload")
async def upload_cookies(
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    try:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="El archivo de cookies está vacío.")
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="El archivo de cookies es demasiado grande.")

        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_bytes(data)
        try:
            os.chmod(COOKIES_DEST, 0o600)
        except Exception:
            pass

        _schedule_cookie_expiry(COOKIES_DEST)
        print(
            f"=== SONORA: temporary YouTube cookies loaded for {COOKIES_TTL_SECONDS // 3600}h ===",
            flush=True,
        )
        return {
            "status": "ok",
            "temporary": True,
            "expires_in_seconds": COOKIES_TTL_SECONDS,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo de cookies.") from exc


@app.post("/api/cookies/b64")
def upload_cookies_b64(
    body: dict = Body(...),
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    b64 = body.get("cookies_b64")
    if not b64:
        raise HTTPException(status_code=400, detail="Proporciona 'cookies_b64' en el cuerpo.")
    try:
        data = base64.b64decode(b64, validate=True)
        if not data:
            raise HTTPException(status_code=400, detail="Las cookies están vacías.")
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Las cookies son demasiado grandes.")
        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_bytes(data)
        try:
            os.chmod(COOKIES_DEST, 0o600)
        except Exception:
            pass
        _schedule_cookie_expiry(COOKIES_DEST)
        return {"status": "ok", "temporary": True, "expires_in_seconds": COOKIES_TTL_SECONDS}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Contenido base64 inválido.") from exc


@app.post("/api/cookies/raw")
def upload_cookies_raw(
    body: dict = Body(...),
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    raw = body.get("cookies")
    if raw is None:
        raise HTTPException(status_code=400, detail="Proporciona 'cookies' en el cuerpo.")
    try:
        if len(raw.encode("utf-8")) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Las cookies son demasiado grandes.")
        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_text(raw)
        try:
            os.chmod(COOKIES_DEST, 0o600)
        except Exception:
            pass
        _schedule_cookie_expiry(COOKIES_DEST)
        return {"status": "ok", "temporary": True, "expires_in_seconds": COOKIES_TTL_SECONDS}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo escribir el archivo de cookies.") from exc


@app.get("/api/cookies/status")
def cookies_status(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    try:
        from downloader import _get_cookie_file
        path = _get_cookie_file()
        return {"cookies_file": path, "exists": (Path(path).is_file() if path else False)}
    except Exception:
        exists = COOKIES_DEST.is_file() and COOKIES_DEST.stat().st_size > 0
        return {"cookies_file": str(COOKIES_DEST) if exists else None, "exists": exists}


@app.post("/api/download")
def download_music(body: DownloadRequest) -> FileResponse:
    temp_dir: Path | None = None
    try:
        file_path, title, uploader = download_audio(body.url, body.format)
        temp_dir = file_path.parent
        clean_title = "".join(char if char.isalnum() or char in " -_" else "_" for char in title).strip()
        clean_uploader = "".join(char if char.isalnum() or char in " -_" else "_" for char in uploader).strip()
        if clean_uploader:
            filename = f"{clean_title or 'audio'} - {clean_uploader}.{body.format.lower()}"
        else:
            filename = f"{clean_title or 'audio'}.{body.format.lower()}"
        media_types = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "opus": "audio/ogg", "wav": "audio/wav"}
        return FileResponse(
            path=file_path,
            media_type=media_types.get(body.format.lower(), "application/octet-stream"),
            filename=filename,
            background=BackgroundTask(_cleanup_temp_dir, temp_dir),
        )
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DownloadFailedError as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/download")
def download_music_get(
    url: str = Query(..., description="Enlace de YouTube"),
    format: str = Query(default="mp3", description="Formato de audio"),
) -> FileResponse:
    return download_music(DownloadRequest(url=url, format=format))


def _cleanup_temp_dir(temp_dir: Path) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
