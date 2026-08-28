from __future__ import annotations

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


COOKIES_DEST = Path("/app/cookies.txt")


@app.post("/api/cookies/upload")
async def upload_cookies(file: UploadFile = File(...), authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    try:
        data = await file.read()
        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_bytes(data)
        try:
            os.chmod(COOKIES_DEST, 0o600)
        except Exception:
            pass
        return {"status": "ok", "path": str(COOKIES_DEST)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo de cookies.") from exc


@app.post("/api/cookies/b64")
def upload_cookies_b64(body: dict = Body(...), authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    b64 = body.get("cookies_b64")
    if not b64:
        raise HTTPException(status_code=400, detail="Proporciona 'cookies_b64' en el cuerpo.")
    try:
        data = base64.b64decode(b64)
        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_bytes(data)
        try:
            os.chmod(COOKIES_DEST, 0o600)
        except Exception:
            pass
        return {"status": "ok", "path": str(COOKIES_DEST)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Contenido base64 inválido.") from exc


@app.post("/api/cookies/raw")
def upload_cookies_raw(body: dict = Body(...), authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    raw = body.get("cookies")
    if raw is None:
        raise HTTPException(status_code=400, detail="Proporciona 'cookies' en el cuerpo.")
    try:
        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_text(raw)
        try:
            os.chmod(COOKIES_DEST, 0o600)
        except Exception:
            pass
        return {"status": "ok", "path": str(COOKIES_DEST)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo escribir el archivo de cookies.") from exc


@app.get("/api/cookies/status")
def cookies_status(authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    provided = authorization or x_api_key
    if not _is_api_key_valid(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    try:
        from downloader import _get_cookie_file
        path = _get_cookie_file()
        return {"cookies_file": path, "exists": (Path(path).is_file() if path else False)}
    except Exception:
        return {"cookies_file": None, "exists": False}


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
        return FileResponse(path=file_path, media_type=media_types.get(body.format.lower(), "application/octet-stream"), filename=filename, background=BackgroundTask(_cleanup_temp_dir, temp_dir))
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DownloadFailedError as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/download")
def download_music_get(url: str = Query(..., description="Enlace de YouTube"), format: str = Query(default="mp3", description="Formato de audio")) -> FileResponse:
    return download_music(DownloadRequest(url=url, format=format))


def _cleanup_temp_dir(temp_dir: Path) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
