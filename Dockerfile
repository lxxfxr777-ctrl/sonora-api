FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DENO_NO_PROMPT=1 \
    DENO_NO_UPDATE_CHECK=1 \
    DENO_DIR=/opt/deno-cache

# =========================================================
# DEPENDENCIAS DEL SISTEMA
# =========================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        unzip \
        git \
        nodejs \
        npm \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# DENO
# =========================================================

RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && mv /root/.deno/bin/deno /usr/local/bin/deno \
    && deno --version

# =========================================================
# DIRECTORIO DE LA APLICACIÓN
# =========================================================

WORKDIR /app

# =========================================================
# DEPENDENCIAS PYTHON
# =========================================================

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# =========================================================
# BGUTIL PO TOKEN PROVIDER
# =========================================================
#
# El servidor bgutil funciona en el puerto 4416.
# Se compila dentro de la misma imagen para que:
#
# SONORA API
#      |
#      +---- yt-dlp
#      |
#      +---- bgutil :4416
#
# =========================================================

RUN git clone \
        --depth 1 \
        --branch 1.3.2 \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
        /opt/bgutil-ytdlp-pot-provider

WORKDIR /opt/bgutil-ytdlp-pot-provider/server

RUN npm ci --omit=dev \
    && npx tsc

# =========================================================
# VOLVER A LA APLICACIÓN
# =========================================================

WORKDIR /app

COPY . .

# =========================================================
# SEGURIDAD PARA COOKIES
# =========================================================

RUN if [ -f /app/cookies.txt ]; then \
        chmod 600 /app/cookies.txt || true; \
    fi

# =========================================================
# CACHE DENO
# =========================================================

RUN mkdir -p /opt/deno-cache

# =========================================================
# PUERTO DE RENDER
# =========================================================

EXPOSE 10000

# =========================================================
# ARRANQUE
# =========================================================
#
# Primero:
#   bgutil PO Token Provider -> puerto 4416
#
# Después:
#   FastAPI -> puerto PORT de Render
#
# =========================================================

CMD ["sh", "-c", "\
    node /opt/bgutil-ytdlp-pot-provider/server/build/main.js --port 4416 & \
    BGUTIL_PID=$!; \
    echo '[bgutil] PO Token Provider iniciado en http://127.0.0.1:4416'; \
    sleep 2; \
    if ! kill -0 $BGUTIL_PID 2>/dev/null; then \
        echo '[bgutil] ERROR: el proveedor PO Token no pudo iniciarse'; \
        exit 1; \
    fi; \
    echo '[sonora] Iniciando FastAPI...'; \
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} \
"]
