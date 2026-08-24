from __future__ import annotations

import colorsys
from io import BytesIO
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image

DEFAULT_PALETTE: dict[str, str] = {
    "accent": "#FF1E10",
    "accent_hover": "#FF4A3A",
    "accent_deep": "#B40A00",
    "accent_soft": "rgba(255, 30, 16, 0.45)",
    "accent_glow": "rgba(255, 30, 16, 0.85)",
    "bg_top": "rgba(255, 30, 16, 0.55)",
    "bg_side": "rgba(180, 10, 0, 0.35)",
    "aurora_1": "#FF6A55",
    "aurora_2": "#FF1E10",
    "aurora_3": "#8A0A00",
}


COVER_HOSTS = (
    "ytimg.com",
    "ggpht.com",
    "googleusercontent.com",
    "youtube.com",
    "youtu.be",
)


def is_allowed_cover_host(host: str | None) -> bool:
    if not host:
        return False
    host = host.lower()
    return any(host == domain or host.endswith("." + domain) for domain in COVER_HOSTS)


def best_thumbnail_url(info: dict[str, Any]) -> str | None:
    thumbs = info.get("thumbnails") or []
    if thumbs:
        best = max(
            thumbs,
            key=lambda item: (item.get("height") or 0) * (item.get("width") or 0),
        )
        return best.get("url") or info.get("thumbnail")
    return info.get("thumbnail")


def fetch_cover_bytes(thumbnail_url: str) -> tuple[bytes, str]:
    request = Request(
        thumbnail_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SonoraPalette/1.0)"},
    )
    with urlopen(request, timeout=10) as response:
        data = response.read()
        content_type = response.headers.get_content_type() or "image/jpeg"
    return data, content_type


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _rgba(r: int, g: int, b: int, alpha: float) -> str:
    return f"rgba({r}, {g}, {b}, {alpha})"


def _from_hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, _clamp(s), _clamp(v))
    return int(r * 255), int(g * 255), int(b * 255)


def _to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)


def _vividize(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Fuerza el color más vivo posible manteniendo el tono."""
    h, s, v = _to_hsv(r, g, b)
    # Si viene muy apagado, igual lo empujamos a un acento usable.
    s = max(s, 0.72)
    v = _clamp(max(v, 0.78), 0.72, 0.98)
    s = _clamp(s * 1.35, 0.78, 1.0)
    return _from_hsv(h, s, v)


def _pick_dominant_vivid(image: Image.Image) -> tuple[int, int, int]:
    """Elige el color más presente y vivo de la portada."""
    sample = image.convert("RGB").resize((64, 64), Image.Resampling.BOX)
    buckets: dict[tuple[int, int, int], float] = {}

    for r, g, b in sample.getdata():
        h, s, v = _to_hsv(r, g, b)
        # Ignora casi negros, blancos y grises muertos.
        if v < 0.14 or v > 0.97 or s < 0.12:
            continue
        # Prioriza presencia + saturación + brillo medio-alto.
        weight = (1.0 + s * 2.4) * (0.55 + min(v, 0.9))
        key = (r // 16 * 16, g // 16 * 16, b // 16 * 16)
        buckets[key] = buckets.get(key, 0.0) + weight

    if not buckets:
        center = image.convert("RGB").resize((1, 1), Image.Resampling.BOX)
        return center.getpixel((0, 0))

    # Entre los más presentes, quédate con el más vivo.
    top = sorted(buckets.items(), key=lambda item: item[1], reverse=True)[:12]
    best_color = top[0][0]
    best_vivid = -1.0
    for color, presence in top:
        _h, s, v = _to_hsv(*color)
        vivid = presence * (0.35 + s) * (0.4 + v)
        if vivid > best_vivid:
            best_vivid = vivid
            best_color = color
    return best_color


def detect_cover_tone(image: Image.Image) -> str:
    sample = image.convert("RGB").resize((32, 32), Image.Resampling.BOX)
    saturations: list[float] = []
    values: list[float] = []
    for r, g, b in sample.getdata():
        _h, s, v = _to_hsv(r, g, b)
        saturations.append(s)
        values.append(v)
    mean_s = sum(saturations) / len(saturations)
    mean_v = sum(values) / len(values)
    if mean_s < 0.16:
        if mean_v < 0.34:
            return "black"
        if mean_v > 0.72:
            return "white"
    return "color"


def _mono_palette(tone: str) -> dict[str, str]:
    if tone == "black":
        return {
            "accent": "#111111",
            "accent_hover": "#2A2A2A",
            "accent_deep": "#000000",
            "accent_soft": "rgba(0, 0, 0, 0.18)",
            "accent_glow": "rgba(0, 0, 0, 0.28)",
            "bg_top": "rgba(255, 255, 255, 0.95)",
            "bg_side": "rgba(230, 230, 230, 0.9)",
            "aurora_1": "#FFFFFF",
            "aurora_2": "#F0F0F0",
            "aurora_3": "#D0D0D0",
            "tone": "black",
        }
    return {
        "accent": "#F5F5F5",
        "accent_hover": "#FFFFFF",
        "accent_deep": "#C8C8C8",
        "accent_soft": "rgba(255, 255, 255, 0.28)",
        "accent_glow": "rgba(255, 255, 255, 0.55)",
        "bg_top": "rgba(255, 255, 255, 0.55)",
        "bg_side": "rgba(230, 230, 230, 0.35)",
        "aurora_1": "#FFFFFF",
        "aurora_2": "#F4F4F4",
        "aurora_3": "#D9D9D9",
        "tone": "white",
    }


def build_palette_from_primary(primary: tuple[int, int, int]) -> dict[str, str]:
    accent = _vividize(*primary)
    h, _s, _v = _to_hsv(*accent)

    # Tres degradados del mismo color principal (claro → medio → profundo).
    light = _from_hsv(h, 0.85, 0.98)
    mid = accent
    deep = _from_hsv(h, 0.95, 0.55)
    hover = _from_hsv(h, 0.9, 1.0)
    deep_btn = _from_hsv(h, 0.92, 0.48)

    ar, ag, ab = accent
    lr, lg, lb = light
    dr, dg, db = deep

    return {
        "accent": _rgb_to_hex(*accent),
        "accent_hover": _rgb_to_hex(*hover),
        "accent_deep": _rgb_to_hex(*deep_btn),
        "accent_soft": _rgba(ar, ag, ab, 0.45),
        "accent_glow": _rgba(ar, ag, ab, 0.85),
        "bg_top": _rgba(lr, lg, lb, 0.55),
        "bg_side": _rgba(dr, dg, db, 0.4),
        "aurora_1": _rgb_to_hex(*light),
        "aurora_2": _rgb_to_hex(*mid),
        "aurora_3": _rgb_to_hex(*deep),
        "tone": "color",
    }


def extract_palette_from_thumbnail(thumbnail_url: str | None) -> dict[str, str]:
    if not thumbnail_url:
        return dict(DEFAULT_PALETTE)

    try:
        request = Request(
            thumbnail_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SonoraPalette/1.0)"},
        )
        with urlopen(request, timeout=8) as response:
            data = response.read()
        image = Image.open(BytesIO(data))
        tone = detect_cover_tone(image)
        if tone in {"black", "white"}:
            return _mono_palette(tone)
        return build_palette_from_primary(_pick_dominant_vivid(image))
    except (URLError, OSError, ValueError, TimeoutError):
        return dict(DEFAULT_PALETTE)


def attach_palette(info: dict[str, Any]) -> dict[str, Any]:
    info = dict(info)
    info["palette"] = extract_palette_from_thumbnail(info.get("thumbnail"))
    return info
