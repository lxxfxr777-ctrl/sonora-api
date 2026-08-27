#!/bin/sh
set -eu

BGUTIL_PORT="4416"
WORKER_PORT="8787"
PUBLIC_PORT="${PORT:-10000}"

cleanup() {
  echo "=== SONORA: shutting down ==="
  if [ -n "${WORKER_PID:-}" ]; then kill "$WORKER_PID" 2>/dev/null || true; fi
  if [ -n "${BGUTIL_PID:-}" ]; then kill "$BGUTIL_PID" 2>/dev/null || true; fi
}
trap cleanup INT TERM EXIT

echo "=== SONORA: starting bgutil ==="
node /opt/bgutil/server/build/main.js --port "$BGUTIL_PORT" &
BGUTIL_PID=$!

READY=0
for i in $(seq 1 60); do
  if ! kill -0 "$BGUTIL_PID" 2>/dev/null; then
    echo "[ERROR] bgutil exited before becoming ready"
    exit 1
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:${BGUTIL_PORT}/ping" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "[ERROR] bgutil did not become ready after 60 seconds"
  exit 1
fi

echo "[OK] bgutil on 127.0.0.1:${BGUTIL_PORT}"
echo "=== SONORA: starting local worker ==="
python -m uvicorn worker:app --host 127.0.0.1 --port "$WORKER_PORT" &
WORKER_PID=$!

READY=0
for i in $(seq 1 30); do
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    echo "[ERROR] worker exited during startup"
    exit 1
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:${WORKER_PORT}/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "[ERROR] worker did not become ready after 30 seconds"
  exit 1
fi

echo "[OK] worker on 127.0.0.1:${WORKER_PORT}"
echo "=== SONORA: starting public API on 0.0.0.0:${PUBLIC_PORT} ==="
exec uvicorn main:app --host 0.0.0.0 --port "$PUBLIC_PORT"
