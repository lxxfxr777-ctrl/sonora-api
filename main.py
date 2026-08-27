from __future__ import annotations

import base64
import os
import re
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from downloader import DownloadFailedError, InvalidYouTubeURLError, download_audio, get_video_info
from youtube_search import YouTubeSearchError, search_videos, video_metadata

STATIC_DIR = Path(__file__).parent

app = FastAPI(title="Sonora Music API", description="Búsqueda de canciones y descarga de audio en Render.", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Enlace interno del resultado seleccionado")
    format: str = Field(default="mp3", description="Formato de audio: mp3, m4a, opus, wav")


def _is_api_key_valid(provided: str | None) -> bool:
    required = os.environ.get("YTDLP_COOKIES_API_KEY")
    if not required:
        return True
    if not provided:
        return False
    if provided.lower().startswith("bearer "):
        provided = provided.split(None, 1)[1].strip()
    return provided == required


def _video_id_from_url(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if host == "youtu.be":
            return parsed.path.strip("/").split("/")[0] or None
        if host.endswith("youtube.com"):
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [None])[0]
            match = re.match(r"^/(?:shorts|embed)/([^/?]+)", parsed.path)
            return match.group(1) if match else None
    except Exception:
        pass
    return None


def _iso_duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    return int(match.group(1) or 0) * 3600 + int(match.group(2) or 0) * 60 + int(match.group(3) or 0)


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace('<script src="/app.js"></script>', '<script src="/search_ui.js"></script>\n  <script src="/app.js"></script>', 1)
    html = html.replace("Pega el link, mira la portada y descarga tu canción.", "Busca una canción por nombre, mira la portada y elige qué quieres escuchar.")
    html = html.replace("Enlace de YouTube / YouTube Music", "Busca una canción")
    html = html.replace('type="url"\n            class="url-input"\n            placeholder="https://www.youtube.com/watch?v=... o music.youtube.com/..."', 'type="text"\n            class="url-input"\n            placeholder="Ej.: Bad Bunny Monaco"')
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "search": "youtube-data-api" if os.getenv("YOUTUBE_API_KEY") else "not-configured", "download": "render-worker"}


@app.get("/api")
def api_root() -> dict:
    return {"message": "Sonora Music API", "docs": "/docs", "search": "/api/search?q=nombre+artista", "info": "/api/info?url=https://www.youtube.com/watch?v=...", "download": "/api/download"}


@app.get("/api/search")
def search_api(q: str = Query(..., min_length=2, max_length=100), limit: int = Query(default=8, ge=1, le=10)) -> dict:
    try:
        return {"ok": True, "query": q.strip(), "results": search_videos(q, limit, os.getenv("SONORA_REGION", "CO"))}
    except YouTubeSearchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/info")
def video_info(url: str = Query(..., description="Enlace interno del resultado de búsqueda")) -> dict:
    video_id = _video_id_from_url(url)
    api_error = None
    if video_id and os.getenv("YOUTUBE_API_KEY"):
        try:
            data = video_metadata(video_id)
            normalized = {"id": data.get("id"), "title": data.get("title") or "Sin título", "uploader": data.get("uploader") or "Artista desconocido", "thumbnail": data.get("thumbnail"), "webpage_url": data.get("webpage_url") or url, "duration": _iso_duration_seconds(data.get("duration_iso"))}
            try:
                from palette import attach_palette, best_thumbnail_url
                normalized["thumbnail"] = best_thumbnail_url(normalized)
                normalized = attach_palette(normalized)
            except Exception:
                pass
            return normalized
        except YouTubeSearchError as exc:
            api_error = str(exc)
    try:
        return get_video_info(url)
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DownloadFailedError as exc:
        detail = f"Metadata de YouTube no disponible: {api_error}" if api_error else str(exc)
        raise HTTPException(status_code=502, detail=detail) from exc


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
        try: os.chmod(COOKIES_DEST, 0o600)
        except Exception: pass
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
        data = base64.b64decode(b64, validate=True)
        COOKIES_DEST.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_DEST.write_bytes(data)
        try: os.chmod(COOKIES_DEST, 0o600)
        except Exception: pass
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
        COOKIES_DEST.write_text(raw, encoding="utf-8")
        try: os.chmod(COOKIES_DEST, 0o600)
        except Exception: pass
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
        return {"cookies_file": path, "exists": Path(path).is_file() if path else False}
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
        filename = f"{clean_title or 'audio'} - {clean_uploader}.{body.format.lower()}" if clean_uploader else f"{clean_title or 'audio'}.{body.format.lower()}"
        media_types = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "opus": "audio/ogg", "wav": "audio/wav"}
        return FileResponse(path=file_path, media_type=media_types.get(body.format.lower(), "application/octet-stream"), filename=filename, background=BackgroundTask(_cleanup_temp_dir, temp_dir))
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DownloadFailedError as exc:
        if temp_dir: shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/download")
def download_music_get(url: str = Query(..., description="Enlace interno del resultado"), format: str = Query(default="mp3", description="Formato de audio")) -> FileResponse:
    return download_music(DownloadRequest(url=url, format=format))


def _cleanup_temp_dir(temp_dir: Path) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
