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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentación:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

## Publicar en Render

Este proyecto ya incluye:

- `Dockerfile`: instala Python, dependencias y FFmpeg.
- `.dockerignore`: evita subir `.venv`, cachés y archivos descargados.
- `render.yaml`: configura un Web Service gratuito con health check.
- La aplicación escucha en `0.0.0.0` y usa la variable `PORT` de Render.

### Opción recomendada: GitHub + Render

1. Sube el contenido de este proyecto a un repositorio de GitHub.
2. En Render crea **New → Blueprint** y conecta el repositorio.
3. Render detectará `render.yaml`.
4. Aplica el Blueprint.
5. Espera a que termine el primer deploy.
6. Abre la URL `https://<tu-servicio>.onrender.com`.
7. Comprueba `/health` y `/docs`.

No necesitas ngrok para el despliegue.

## Rutas principales

- `GET /` — interfaz web Sonora.
- `GET /health` — comprobación de estado.
- `GET /api` — información de la API.
- `GET /api/info?url=...` — información del video.
- `GET /api/cover?src=...` — proxy de portada.
- `GET /api/download?url=...&format=mp3` — descarga.
- `POST /api/download` — descarga con JSON `{ "url": "...", "format": "mp3" }`.
- `GET /docs` — Swagger/OpenAPI.

## Nota sobre Render Free

El servicio gratuito de Render se duerme después de un periodo de inactividad y puede tardar en despertar con la primera solicitud. Además, el sistema de archivos del servicio es temporal. La aplicación usa carpetas temporales para las descargas, por lo que no depende de conservar los archivos descargados entre reinicios.

## FFmpeg

FFmpeg se instala dentro de la imagen Docker. No es necesario instalar FFmpeg en el servidor manualmente.

## Importante

La API queda públicamente accesible al desplegarla como Web Service. Si el uso crece, conviene añadir autenticación, límites de uso y/o protección contra abuso antes de utilizarla como servicio de producción.
