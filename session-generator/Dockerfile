# Render-safe wrapper around the official always-running session generator.
# Render runs image services as root; Chromium needs no_sandbox in this setup.
FROM ghcr.io/imputnet/yt-session-generator:webserver

RUN python - <<'PY'
from pathlib import Path
p = Path('/app/potoken_generator/extractor.py')
s = p.read_text()
old = 'nodriver.start(headless=False,\n'
new = 'nodriver.start(headless=False, no_sandbox=True,\n'
if old not in s:
    raise SystemExit('Expected nodriver.start call was not found')
p.write_text(s.replace(old, new, 1))
PY

EXPOSE 10000

CMD ["/bin/sh", "-c", "Xvfb :99 -ac -screen 0 ${XVFB_WHD:-1280x720x16} -nolisten tcp >/dev/null 2>&1 & sleep 2; export DISPLAY=:99; exec python /app/potoken-generator.py --bind 0.0.0.0 --port ${PORT:-10000}"]
