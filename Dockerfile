# =========================================================
# ETAPA 1: COMPILAR BGUTIL PO TOKEN PROVIDER
# =========================================================

FROM node:25-bookworm-slim AS bgutil-builder

WORKDIR /bgutil

RUN git clone \
    --depth 1 \
    --branch 1.3.2 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    .

WORKDIR /bgutil/server

# Instalamos TODAS las dependencias, incluyendo TypeScript.
# No usamos --omit=dev porque TypeScript está entre las
# dependencias necesarias para compilar el servidor.
RUN npm ci --no-audit --no-fund

RUN npx tsc


# =========================================================
# ETAPA 2: SONORA API
# =========================================================

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
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# =========================================================
# DENO
# =========================================================

RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && mv /root/.deno/bin/deno /usr/local/bin/deno \
    && deno --version


# =========================================================
# APLICACIÓN SONORA
# =========================================================

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install \
        --no-cache-dir \
        --upgrade pip \
    && python -m pip install \
        --no-cache-dir \
        -r requirements.txt


# =========================================================
# BGUTIL
# =========================================================
#
# Copiamos el servidor ya compilado desde la primera etapa.
#
# El servidor oficial utiliza:
#
#   build/main.js
#
# y escucha en:
#
#   4416
#
# =========================================================

COPY --from=bgutil-builder \
    /bgutil/server/build \
    /opt/bgutil/server/build

COPY --from=bgutil-builder \
    /bgutil/server/node_modules \
    /opt/bgutil/server/node_modules

COPY --from=bgutil-builder \
    /bgutil/server/package.json \
    /opt/bgutil/server/package.json

COPY --from=bgutil-builder \
    /bgutil/server/package-lock.json \
    /opt/bgutil/server/package-lock.json


# =========================================================
# CÓDIGO DE SONORA
# =========================================================

COPY . .


# =========================================================
# SEGURIDAD DE COOKIES
# =========================================================

RUN if [ -f /app/cookies.txt ]; then \
        chmod 600 /app/cookies.txt || true; \
    fi


# =========================================================
# CACHE DENO
# =========================================================

RUN mkdir -p /opt/deno-cache


# =========================================================
# PUERTO
# =========================================================

EXPOSE 10000


# =========================================================
# ARRANQUE
# =========================================================
#
# PROCESO 1:
#   bgutil PO Token Provider
#   http://127.0.0.1:4416
#
# PROCESO 2:
#   FastAPI / SONORA
#   http://0.0.0.0:${PORT}
#
# =========================================================

CMD ["sh", "-c", "\
    echo '========================================'; \
    echo ' SONORA - INICIANDO BGUTIL PO PROVIDER'; \
    echo '========================================'; \
    node /opt/bgutil/server/build/main.js --port 4416 & \
    BGUTIL_PID=$!; \
    sleep 3; \
    if ! kill -0 $BGUTIL_PID 2>/dev/null; then \
        echo '[ERROR] bgutil no pudo iniciarse'; \
        exit 1; \
    fi; \
    echo '[OK] bgutil ejecutándose en 127.0.0.1:4416'; \
    echo '========================================'; \
    echo ' SONORA - INICIANDO FASTAPI'; \
    echo '========================================'; \
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} \
"]
