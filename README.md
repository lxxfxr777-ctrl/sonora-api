# Sonora — YouTube Music API

API FastAPI para consultar información de videos de YouTube/YouTube Music y descargar audio en MP3, M4A, OPUS o WAV.

## Arquitectura actual

Sonora está diseñada para funcionar como **un solo Web Service de Render**:

```text
Sonora / FastAPI
       |
       v
worker local
       |
       +--> yt-dlp
       |
       +--> bgutil PO Token provider (127.0.0.1:4416)
       |
       +--> FFmpeg
       |
       v
    YouTube
```

El worker y el proveedor bgutil viven dentro del mismo contenedor. Esto evita depender de Cobalt, de un segundo servicio público o de un generador remoto de sesiones de YouTube.

## Ejecutar localmente

Requisitos:

- Python 3.12+
- FFmpeg
- Node.js 20+
- Deno

Instala dependencias:

```powershell
pip install -r requirements.txt
```

Inicia:

```powershell
python start.py
```

Documentación:

- `http://127.0.0.1:10000/docs`
- `http://127.0.0.1:10000/health`

## Publicar en Render

El repositorio incluye un `render.yaml` que configura un único Web Service Docker.

El `Dockerfile` compila el servidor bgutil y arranca, dentro del mismo contenedor:

1. bgutil en `127.0.0.1:4416`
2. worker FastAPI en `127.0.0.1:8787`
3. API pública FastAPI en `$PORT`

Render solo necesita desplegar el servicio definido en `render.yaml`.

## Descargas de YouTube

El descargador usa yt-dlp con bgutil para obtener automáticamente PO Tokens cuando son necesarios. La primera estrategia es `mweb` + bgutil y después se prueban clientes alternativos si ese perfil no puede obtener los formatos necesarios.

Los perfiles se pueden cambiar mediante:

```text
YTDLP_PLAYER_PROFILES=mweb;web_safari;tv_embedded;web_embedded;android_vr
```

No se necesitan cookies para los videos públicos que puedan descargarse sin una sesión de cuenta. Las cookies son un mecanismo opcional para contenido que realmente requiere autenticación.

## Cookies de YouTube

Si un contenido concreto necesita una sesión autenticada, puedes configurar:

- `YTDLP_COOKIES_B64`
- `YTDLP_COOKIES_FILE`
- `YTDLP_USE_COOKIES=true`

Por defecto `YTDLP_USE_COOKIES=false`.

No conviene depender de cookies para el funcionamiento normal del servicio porque YouTube puede rotarlas o invalidarlas.

## Rutas principales

- `GET /` — interfaz web Sonora.
- `GET /health` — comprobación de estado.
- `GET /api` — información de la API.
- `GET /api/info?url=...` — información del video.
- `GET /api/cover?src=...` — proxy de portada.
- `GET /api/download?url=...&format=mp3` — descarga.
- `POST /api/download` — descarga con JSON `{ "url": "...", "format": "mp3" }`.
- `GET /docs` — Swagger/OpenAPI.

## Render Free

El servicio gratuito de Render puede suspenderse después de un periodo de inactividad y tardar en despertar con la primera solicitud. Eso es independiente de la descarga.

El sistema de archivos del servicio es temporal. Las descargas se guardan temporalmente y se eliminan después de enviarse al usuario.

## FFmpeg y bgutil

FFmpeg se instala dentro de la imagen Docker.

El proveedor bgutil se compila durante el build y se inicia dentro del mismo contenedor en `127.0.0.1:4416`. La versión del servidor se mantiene alineada con `bgutil-ytdlp-pot-provider==1.3.2` instalado en `requirements.txt`.

## Importante

La API queda públicamente accesible al desplegarla como Web Service. Si el uso crece, conviene añadir autenticación, límites de uso y/o protección contra abuso antes de utilizarla como servicio de producción.
