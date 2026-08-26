FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DENO_NO_PROMPT=1 \
    DENO_NO_UPDATE_CHECK=1 \
    DENO_DIR=/opt/deno-cache

# Dependencias del sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        unzip \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# DENO
# ---------------------------------------------------------
# Deno >= 2.0 es compatible con el proveedor bgutil
# y también sirve como runtime JavaScript para yt-dlp.
RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && mv /root/.deno/bin/deno /usr/local/bin/deno \
    && deno --version

WORKDIR /app

# ---------------------------------------------------------
# PYTHON DEPENDENCIES
# ---------------------------------------------------------
COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------
# BGUTIL PO TOKEN PROVIDER
# ---------------------------------------------------------
# Descargamos exactamente la misma versión del proveedor
# que utilizaremos mediante el paquete Python.
RUN git clone \
        --depth 1 \
        --branch 1.3.2 \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
        /opt/bgutil-ytdlp-pot-provider

# Instalamos las dependencias del servidor Deno.
RUN cd /opt/bgutil-ytdlp-pot-provider/server \
    && deno install --allow-scripts=npm:canvas --frozen

# ---------------------------------------------------------
# APPLICATION
# ---------------------------------------------------------
COPY . .

# Seguridad para cookies si existieran.
RUN if [ -f /app/cookies.txt ]; then \
        chmod 600 /app/cookies.txt || true; \
    fi

# Cache de Deno
RUN mkdir -p /opt/deno-cache

EXPOSE 10000

# ---------------------------------------------------------
# START
# ---------------------------------------------------------
# 1. Arranca bgutil en el puerto 4416.
# 2. Después arranca FastAPI en el puerto de Render.
#
# Ambos procesos viven dentro del mismo contenedor, por lo
# que yt-dlp podrá comunicarse con:
#
# http://127.0.0.1:4416
# ---------------------------------------------------------
CMD ["sh", "-c", "\
    cd /opt/bgutil-ytdlp-pot-provider/server/node_modules && \
    deno run \
        --allow-env \
        --allow-net \
        --allow-ffi=. \
        --allow-read=. \
        ../src/main.ts --port 4416 & \
    echo '[bgutil] PO Token Provider iniciado en http://127.0.0.1:4416' && \
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} \
"]
