import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="Sonora YouTube Worker")

WORKER_TOKEN = os.getenv("WORKER_TOKEN", "").strip()
ALLOWED_FORMATS = {"mp3": "mp3", "m4a": "m4a", "opus": "opus", "wav": "wav"}
COOKIES_FILE = Path(os.getenv("YTDLP_COOKIES_FILE", "/app/cookies.txt"))

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp3"

def check_token(authorization: Optional[str]) -> None:
    if not WORKER_TOKEN:
        return
    if authorization != f"Bearer {WORKER_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

def clean_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    if not any(host in url for host in ("youtube.com/", "youtu.be/", "music.youtube.com/")):
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported")
    return url

def _base_options() -> dict:
    options = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
    }
    # Use the same cookies uploaded through Sonora when available.
    if COOKIES_FILE.is_file() and COOKIES_FILE.stat().st_size > 0:
        options["cookiefile"] = str(COOKIES_FILE)
    return options

def ytdlp_info_options() -> dict:
    options = _base_options()
    options["skip_download"] = True
    return options

def ytdlp_download_options(workdir: Path, fmt: str) -> dict:
    options = _base_options()
    options.update({
        "outtmpl": str(workdir / "%(title).120s-%(id)s.%(ext)s"),
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": ALLOWED_FORMATS[fmt],
            "preferredquality": "192",
        }],
    })
    return options

@app.get("/")
def root():
    return {"status": "ok", "service": "sonora-worker", "youtube": "render-local-worker"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/info")
def info(request: InfoRequest, authorization: Optional[str] = Header(default=None)):
    check_token(authorization)
    url = clean_url(request.url)
    try:
        with yt_dlp.YoutubeDL(ytdlp_info_options()) as ydl:
            data = ydl.extract_info(url, download=False)
        return {
            "ok": True,
            "id": data.get("id"),
            "title": data.get("title"),
            "uploader": data.get("uploader"),
            "channel": data.get("channel"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "webpage_url": data.get("webpage_url") or url,
            "description": data.get("description"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

@app.post("/download")
def download(request: DownloadRequest, authorization: Optional[str] = Header(default=None)):
    check_token(authorization)
    url = clean_url(request.url)
    fmt = request.format.lower().strip()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported format. Use mp3, m4a, opus or wav.")

    workdir = Path(tempfile.mkdtemp(prefix="sonora-worker-"))
    try:
        with yt_dlp.YoutubeDL(ytdlp_download_options(workdir, fmt)) as ydl:
            data = ydl.extract_info(url, download=True)
        files = [p for p in workdir.iterdir() if p.is_file() and p.suffix.lower() == f".{fmt}"]
        if not files:
            raise RuntimeError("yt-dlp completed but no converted audio file was produced.")
        audio_file = files[0]
        return FileResponse(path=str(audio_file), filename=f"{data.get('title') or 'audio'}.{fmt}", media_type="application/octet-stream")
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("worker:app", host="127.0.0.1", port=8787, reload=False)
