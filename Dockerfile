# =========================================================
# ETAPA 1 - COMPILAR BGUTIL PO TOKEN PROVIDER
# =========================================================

FROM node:25-bookworm-slim AS bgutil-builder

# Instalar Git porque vamos a descargar bgutil desde GitHub
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bgutil

# IMPORTANTE:
# El repositorio actualmente tiene disponible el tag 1.3.1.
# El plugin Python 1.3.2 se mantiene instalado aparte.
RUN git clone \
    --depth 1 \
    --single-branch \
    --branch 1.3.1 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    .

WORKDIR /bgutil/server

# Instalar dependencias
RUN npm ci --no-audit --no-fund

# Compilar TypeScript
RUN npx tsc


# =========================================================
# ETAPA 2 - SONORA
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
# COPIAR BGUTIL COMPILADO
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
# CÓDIGO SONORA
# =========================================================

COPY . .


# =========================================================
# COOKIES OPCIONALES
# =========================================================

RUN if [ -f /app/cookies.txt ]; then \
        chmod 600 /app/cookies.txt || true; \
    fi


# =========================================================
# CACHE DENO
# =========================================================

RUN mkdir -p /opt/deno-cache


# =========================================================
# PUERTO RENDER
# =========================================================

EXPOSE 10000


# =========================================================
# ARRANQUE
# =========================================================

CMD ["sh", "-c", "\
    echo '========================================'; \
    echo ' INICIANDO BGUTIL PO TOKEN PROVIDER'; \
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
    echo ' INICIANDO SONORA FASTAPI'; \
    echo '========================================'; \
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} \
"]
