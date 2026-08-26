# =========================================================
# ETAPA 1 - COMPILAR BGUTIL PO TOKEN PROVIDER
# =========================================================

FROM node:25-bookworm-slim AS bgutil-builder

# Git es necesario para descargar bgutil
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bgutil

# La versión 1.3.1 es la versión del servidor disponible
# como tag en el repositorio.
RUN git clone \
    --depth 1 \
    --single-branch \
    --branch 1.3.1 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    .

WORKDIR /bgutil/server

# Instalar dependencias completas porque necesitamos
# TypeScript para compilar el servidor.
RUN npm ci \
    --no-audit \
    --no-fund

# Compilar TypeScript
RUN npx tsc


# =========================================================
# ETAPA 2 - SONORA API
# =========================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_PATH=/usr/local/lib/node_modules

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
# COPIAR NODE.JS DESDE LA IMAGEN OFICIAL
# =========================================================

COPY --from=bgutil-builder /usr/local/bin/node /usr/local/bin/node

COPY --from=bgutil-builder /usr/local/lib/node_modules /usr/local/lib/node_modules


# Crear enlaces para que node esté disponible
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version \
    && npm --version


# =========================================================
# SONORA
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
# BGUTIL COMPILADO
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


# =========================================================
# CÓDIGO DE SONORA
# =========================================================

COPY . .


# =========================================================
# COOKIES OPCIONALES
# =========================================================

RUN if [ -f /app/cookies.txt ]; then \
        chmod 600 /app/cookies.txt || true; \
    fi


# =========================================================
# PUERTO
# =========================================================

EXPOSE 10000


# =========================================================
# ARRANQUE
# =========================================================
#
# PROCESO 1:
# BGUTIL
# http://127.0.0.1:4416
#
# PROCESO 2:
# FASTAPI
# http://0.0.0.0:${PORT}
#
# =========================================================

CMD ["sh", "-c", "\
    echo '========================================'; \
    echo ' SONORA - BGUTIL PO TOKEN PROVIDER'; \
    echo '========================================'; \
    node /opt/bgutil/server/build/main.js --port 4416 & \
    BGUTIL_PID=$!; \
    sleep 3; \
    if ! kill -0 $BGUTIL_PID 2>/dev/null; then \
        echo '[ERROR] BGUTIL NO PUDO INICIARSE'; \
        exit 1; \
    fi; \
    echo '[OK] BGUTIL funcionando en 127.0.0.1:4416'; \
    echo '========================================'; \
    echo ' SONORA - FASTAPI'; \
    echo '========================================'; \
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} \
"]
