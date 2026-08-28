from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CobaltDownloadError(RuntimeError):
    pass


def _base_url() -> str:
    return os.getenv("COBALT_URL", "").strip().rstrip("/")


def enabled() -> bool:
    return bool(_base_url())


def _request(url: str, payload: dict, timeout: int = 600) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Sonora/1.0",
    }
    api_key = os.getenv("COBALT_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Api-Key {api_key}"

    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        try:
            raw = exc.read()
            detail = raw.decode("utf-8", errors="replace")[:800]
        except Exception:
            detail = str(exc)
        raise CobaltDownloadError(f"Cobalt respondió HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise CobaltDownloadError(f"No se pudo conectar con Cobalt: {exc}") from exc

    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise CobaltDownloadError("Cobalt devolvió una respuesta que no es JSON válido.") from exc
    if not isinstance(data, dict):
        raise CobaltDownloadError("Cobalt devolvió un JSON inválido.")
    return data


def download(url: str, fmt: str, workdir: Path) -> tuple[Path, str]:
    base = _base_url()
    if not base:
        raise CobaltDownloadError("COBALT_URL no está configurada.")

    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": fmt,
        "audioBitrate": "192",
        "filenameStyle": "pretty",
        "youtubeVideoCodec": "h264",
    }
    data = _request(base + "/", payload)
    status = data.get("status")

    if status == "error":
        raise CobaltDownloadError(str(data.get("text") or data.get("error") or "Cobalt no pudo procesar el enlace."))

    if status != "tunnel" or not data.get("url"):
        raise CobaltDownloadError(f"Cobalt devolvió un estado no utilizable: {status!r}")

    tunnel_url = str(data["url"])
    filename = str(data.get("filename") or f"audio.{fmt}")
    suffix = f".{fmt}"
    if not filename.lower().endswith(suffix):
        filename = Path(filename).stem + suffix

    output = workdir / filename
    request = Request(
        tunnel_url,
        headers={"User-Agent": "Sonora/1.0", "Accept": "*/*"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=600) as response, output.open("wb") as target:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise CobaltDownloadError(f"No se pudo descargar el archivo desde el túnel de Cobalt: {exc}") from exc

    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise CobaltDownloadError("Cobalt devolvió un archivo vacío.")

    return output, filename
