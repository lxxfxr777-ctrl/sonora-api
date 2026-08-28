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
# ETAPA 2 - RUNTIME DENO PARA yt-dlp / YOUTUBE
# =========================================================

FROM denoland/deno:debian-2.6.9 AS deno-runtime

# =========================================================
# ETAPA 3 - SONORA API + WORKER LOCAL
# =========================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_PATH=/usr/local/lib/node_modules \
    YTDLP_POT_PROVIDER_URL=http://127.0.0.1:4416 \
    SONORA_LOCAL_WORKER=true \
    YTDLP_JS_RUNTIME=deno

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bgutil-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=bgutil-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=deno-runtime /usr/bin/deno /usr/local/bin/deno

RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version \
    && npm --version \
    && deno --version

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

# Start everything through Python instead of a multi-line shell command.
# This avoids Render parsing the previous command as a literal "[sh" command.
CMD ["python", "/app/start.py"]
