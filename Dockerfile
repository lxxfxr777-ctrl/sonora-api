# =========================================================
# ETAPA 1 - COMPILAR BGUTIL PO TOKEN PROVIDER
# =========================================================

FROM node:25-bookworm-slim AS bgutil-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bgutil
RUN git clone --depth 1 --single-branch --branch 1.3.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git .

WORKDIR /bgutil/server
RUN npm ci --no-audit --no-fund
RUN npx tsc

# =========================================================
# ETAPA 2 - SONORA API + WORKER LOCAL
# =========================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_PATH=/usr/local/lib/node_modules \
    YTDLP_POT_PROVIDER_URL=http://127.0.0.1:4416 \
    SONORA_LOCAL_WORKER=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bgutil-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=bgutil-builder /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --from=bgutil-builder /bgutil/server/build /opt/bgutil/server/build
COPY --from=bgutil-builder /bgutil/server/node_modules /opt/bgutil/server/node_modules
COPY --from=bgutil-builder /bgutil/server/package.json /opt/bgutil/server/package.json

COPY . .

RUN if [ -f /app/cookies.txt ]; then chmod 600 /app/cookies.txt || true; fi

EXPOSE 10000

# Start bgutil, the local YouTube worker, then the public Sonora API.
CMD ["sh", "-c", "\
    echo '=== SONORA: starting bgutil ==='; \
    node /opt/bgutil/server/build/main.js --port 4416 & BGUTIL_PID=$!; \
    sleep 3; \
    kill -0 $BGUTIL_PID 2>/dev/null || { echo '[ERROR] BGUTIL failed'; exit 1; }; \
    echo '[OK] bgutil on 127.0.0.1:4416'; \
    echo '=== SONORA: starting local worker ==='; \
    python -m uvicorn worker:app --host 127.0.0.1 --port 8787 & WORKER_PID=$!; \
    sleep 2; \
    kill -0 $WORKER_PID 2>/dev/null || { echo '[ERROR] WORKER failed'; exit 1; }; \
    echo '[OK] worker on 127.0.0.1:8787'; \
    echo '=== SONORA: starting public API ==='; \
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} \
"]
