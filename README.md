# Sonora — YouTube Music API

API FastAPI para consultar información de videos de YouTube/YouTube Music y descargar audio en MP3, M4A, OPUS o WAV.

## Ejecutar localmente

Requisitos:

- Python 3.12+
- FFmpeg

Instala dependencias:

```powershell
pip install -r requirements.txt
```

Inicia:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentación:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

## Publicar en Render

Este proyecto incluye:

- `Dockerfile`: instala Python, FFmpeg, Node.js y el proveedor bgutil.
- `render.yaml`: configura el Web Service y el health check.
- `downloader.py`: ejecuta yt-dlp directamente dentro del contenedor de Render.
- `main.py`: expone la API y la interfaz web.

El descargador **ya no depende de un worker en Windows ni de un Cloudflare Tunnel**. Render ejecuta el proceso de descarga dentro de su propio contenedor.

### Opción recomendada: GitHub + Render

1. Conecta este repositorio a Render.
2. Usa el `render.yaml` como Blueprint o configura el Web Service con Docker.
3. Espera a que termine el deploy.
4. Abre la URL `https://<tu-servicio>.onrender.com`.
5. Comprueba `/health` y `/docs`.

No necesitas mantener una PC encendida para que el descargador funcione.

## Rutas principales

- `GET /` — interfaz web Sonora.
- `GET /health` — comprobación de estado.
- `GET /api` — información de la API.
- `GET /api/info?url=...` — información del video.
- `GET /api/cover?src=...` — proxy de portada.
- `GET /api/download?url=...&format=mp3` — descarga.
- `POST /api/download` — descarga con JSON `{ "url": "...", "format": "mp3" }`.
- `GET /docs` — Swagger/OpenAPI.

## Cookies de YouTube

Si YouTube exige cookies para determinados videos, puedes configurar en Render `YTDLP_COOKIES_B64` con el contenido base64 de tu `cookies.txt`, o usar `YTDLP_COOKIES_FILE` / el endpoint protegido de subida de cookies.

Si configuras `YTDLP_COOKIES_API_KEY`, usa `Authorization: Bearer <key>` o `X-API-Key: <key>` para los endpoints de cookies.

## Render Free

El servicio gratuito de Render puede dormir después de un periodo de inactividad y puede tardar en despertar con la primera solicitud. Eso es independiente de la descarga: una vez que el contenedor está activo, **el worker ya no está en tu PC** y no necesitas Cloudflare Tunnel ni los comandos de Windows para realizar las descargas.

El sistema de archivos del servicio es temporal. Las descargas se guardan en carpetas temporales y se eliminan después de enviarse al usuario.

## FFmpeg y bgutil

FFmpeg se instala dentro de la imagen Docker.

El proveedor bgutil se compila y se inicia dentro del mismo contenedor en `127.0.0.1:4416`, y `yt-dlp` lo utiliza para sus operaciones de YouTube. La versión del servidor se mantiene alineada con el plugin Python instalado en `requirements.txt`.

## Importante

La API queda públicamente accesible al desplegarla como Web Service. Si el uso crece, conviene añadir autenticación, límites de uso y/o protección contra abuso antes de utilizarla como servicio de producción.
