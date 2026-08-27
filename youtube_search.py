from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeSearchError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise YouTubeSearchError(
            "YOUTUBE_API_KEY no está configurada en Render. Activa YouTube Data API v3 y añade la clave como variable de entorno."
        )
    return key


def _get(path: str, params: dict[str, str]) -> dict:
    query = urlencode(params)
    request = Request(
        f"{API_BASE}/{path}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Sonora/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            message = body.get("error", {}).get("message") or str(exc)
        except Exception:
            message = str(exc)
        raise YouTubeSearchError(f"YouTube Data API: {message}") from exc
    except (URLError, TimeoutError) as exc:
        raise YouTubeSearchError("No se pudo conectar con YouTube Data API.") from exc


def search_videos(query: str, max_results: int = 8, region_code: str = "CO") -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        raise YouTubeSearchError("Escribe al menos 2 caracteres para buscar.")

    max_results = max(1, min(int(max_results), 10))
    data = _get(
        "search",
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": str(max_results),
            "regionCode": region_code,
            "safeSearch": "none",
            "key": _api_key(),
        },
    )

    ids = [item.get("id", {}).get("videoId") for item in data.get("items", [])]
    ids = [video_id for video_id in ids if video_id]
    if not ids:
        return []

    details = _get(
        "videos",
        {
            "part": "snippet,contentDetails",
            "id": ",".join(ids),
            "key": _api_key(),
        },
    )
    by_id = {item.get("id"): item for item in details.get("items", [])}

    results = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        detail = by_id.get(video_id, {})
        duration = detail.get("contentDetails", {}).get("duration")
        results.append({
            "id": video_id,
            "title": snippet.get("title", ""),
            "uploader": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId"),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt"),
            "thumbnail": (
                snippet.get("thumbnails", {}).get("high", {}).get("url")
                or snippet.get("thumbnails", {}).get("medium", {}).get("url")
                or snippet.get("thumbnails", {}).get("default", {}).get("url")
            ),
            "duration_iso": duration,
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return results


def video_metadata(video_id: str) -> dict:
    video_id = video_id.strip()
    if not video_id or len(video_id) > 32:
        raise YouTubeSearchError("ID de vídeo no válido.")

    data = _get(
        "videos",
        {
            "part": "snippet,contentDetails",
            "id": video_id,
            "key": _api_key(),
        },
    )
    items = data.get("items", [])
    if not items:
        raise YouTubeSearchError("No se encontró el vídeo.")

    item = items[0]
    snippet = item.get("snippet", {})
    return {
        "id": video_id,
        "title": snippet.get("title", ""),
        "uploader": snippet.get("channelTitle", ""),
        "channel_id": snippet.get("channelId"),
        "description": snippet.get("description", ""),
        "thumbnail": (
            snippet.get("thumbnails", {}).get("maxres", {}).get("url")
            or snippet.get("thumbnails", {}).get("high", {}).get("url")
            or snippet.get("thumbnails", {}).get("medium", {}).get("url")
        ),
        "duration_iso": item.get("contentDetails", {}).get("duration"),
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }
