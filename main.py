from __future__ import annotations

import shutil
from pathlib import Path

from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
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

# La API puede ser consumida desde otras páginas/aplicaciones.
# Si más adelante quieres restringirla a dominios concretos, cambia
# allow_origins por una lista de dominios permitidos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Enlace de YouTube (video o YouTube Music)")
    format: str = Field(default="mp3", description="Formato de audio: mp3, m4a, opus, wav")


@app.get("/api")
def api_root() -> dict[str, str]:
    return {
        "message": "YouTube Music API",
        "docs": "/docs",
        "endpoints": "/api/info, /api/download",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/info")
def video_info(url: str = Query(..., description="Enlace de YouTube")) -> dict:
    try:
        return get_video_info(url)
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DownloadFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/cover")
def cover_proxy(src: str = Query(..., description="URL de la portada")) -> Response:
    from palette import fetch_cover_bytes, is_allowed_cover_host

    parsed = urlparse(src)
    if parsed.scheme not in {"http", "https"} or not is_allowed_cover_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Portada no válida.")

    try:
        data, content_type = fetch_cover_bytes(src)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No se pudo cargar la portada.") from exc

    return Response(content=data, media_type=content_type)


@app.post("/api/download")
def download_music(body: DownloadRequest) -> FileResponse:
    temp_dir: Path | None = None

    try:
        file_path, title = download_audio(body.url, body.format)
        temp_dir = file_path.parent

        safe_name = "".join(char if char.isalnum() or char in " -_" else "_" for char in title)
        filename = f"{safe_name.strip() or 'audio'}.{body.format.lower()}"

        return FileResponse(
            path=file_path,
            media_type="audio/mpeg" if body.format.lower() == "mp3" else "application/octet-stream",
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


# Sirve la interfaz web (app/static/index.html, style.css, app.js) en "/".
# Se monta al final a propósito: así las rutas de la API definidas arriba
# siempre tienen prioridad y este mount solo atiende lo que no coincidió
# con ninguna ruta anterior.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
