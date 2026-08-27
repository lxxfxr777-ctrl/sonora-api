import base64
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
BGUTIL_URL = os.getenv("YTDLP_POT_PROVIDER_URL", "http://127.0.0.1:4416").rstrip("/")
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "").strip()
YTDLP_COOKIES_B64 = os.getenv("YTDLP_COOKIES_B64", "").strip()

# Keep the recommended mweb client first. web_embedded does not require a PO
# token and can rescue public/embeddable videos when YouTube blocks the normal
# web clients. Extra clients can be supplied in Render with
# YTDLP_PLAYER_CLIENTS=mweb,web_embedded,tv.
PLAYER_CLIENTS = [
    item.strip()
    for item in os.getenv("YTDLP_PLAYER_CLIENTS", "mweb,web_embedded").split(",")
    if item.strip()
]

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
    # YouTube Music and YouTube share the same video IDs. Normalizing the
    # public page avoids an unnecessary Music-specific webpage request.
    url = url.replace("https://music.youtube.com/watch?", "https://www.youtube.com/watch?")
    url = url.replace("http://music.youtube.com/watch?", "https://www.youtube.com/watch?")
    return url

def _ensure_env_cookie_file() -> Optional[Path]:
    """Materialize an optional Render secret containing Netscape cookies."""
    if not YTDLP_COOKIES_B64:
        return None
    try:
        data = base64.b64decode(YTDLP_COOKIES_B64, validate=True)
    except Exception as exc:
        raise RuntimeError("YTDLP_COOKIES_B64 is not valid base64") from exc
    if not data:
        return None
    path = Path(tempfile.gettempdir()) / "sonora-ytdlp-cookies.txt"
    path.write_bytes(data)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path

def _cookie_file() -> Optional[Path]:
    env_cookie_file = _ensure_env_cookie_file()
    if env_cookie_file:
        return env_cookie_file
    if COOKIES_FILE.is_file() and COOKIES_FILE.stat().st_size > 0:
        return COOKIES_FILE
    return None

def _base_options() -> dict:
    # yt-dlp's Python API expects extractor_args as nested dictionaries.
    # IMPORTANT: do NOT append a fake "override" client. It is interpreted as
    # an unsupported YouTube client and was visible as "Skipping unsupported
    # client override" in the Render logs.
    options = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "verbose": True,
        "force_ipv4": True,
        "retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "extractor_args": {
            "youtube": {
                "player_client": PLAYER_CLIENTS,
            },
            "youtubepot-bgutilhttp": {
                "base_url": [BGUTIL_URL],
            },
        },
        "js_runtimes": {
            "deno": {
                "path": os.getenv("DENO_PATH", "/usr/local/bin/deno"),
            }
        },
    }

    cookie_file = _cookie_file()
    if cookie_file:
        options["cookiefile"] = str(cookie_file)

    if YTDLP_PROXY:
        options["proxy"] = YTDLP_PROXY

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
    return {
        "status": "ok",
        "service": "sonora-worker",
        "youtube": "render-local-worker",
        "player_clients": PLAYER_CLIENTS,
        "cookies_configured": _cookie_file() is not None,
        "pot_provider": BGUTIL_URL,
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cookies_configured": _cookie_file() is not None,
        "player_clients": PLAYER_CLIENTS,
    }

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
        return FileResponse(
            path=str(audio_file),
            filename=f"{data.get('title') or 'audio'}.{fmt}",
            media_type="application/octet-stream",
        )
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=502, detail=str(exc))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("worker:app", host="127.0.0.1", port=8787, reload=False)
