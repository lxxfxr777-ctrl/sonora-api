(() => {
  const form = document.getElementById('search-form');
  const urlInput = document.getElementById('url-input');
  const searchBtn = document.getElementById('search-btn');
  const searchError = document.getElementById('search-error');

  const preview = document.getElementById('preview');
  const previewThumb = document.getElementById('preview-thumb');
  const previewTitle = document.getElementById('preview-title');
  const previewArtist = document.getElementById('preview-artist');
  const previewDuration = document.getElementById('preview-duration');
  const previewFormatLabel = document.getElementById('preview-format-label');

  const formatInputs = document.querySelectorAll('input[name="format"]');
  const formatNote = document.getElementById('format-note');

  const downloadBtn = document.getElementById('download-btn');
  const downloadBtnLabel = downloadBtn.querySelector('.download-btn-label');
  const downloadStatus = document.getElementById('download-status');
  const coverStage = document.querySelector('.cover-stage');
  const playBtn = document.getElementById('play-btn');
  const playIcon = document.getElementById('play-icon');
  const pauseIcon = document.getElementById('pause-icon');
  const seekBar = document.getElementById('seek-bar');
  const timeCurrent = document.getElementById('time-current');
  const timeTotal = document.getElementById('time-total');
  const playerNow = document.getElementById('player-now');
  const playerStatus = document.getElementById('player-status');

  let currentUrl = '';
  let currentVideoId = '';
  let ytPlayer = null;
  let ytReady = false;
  let ytApiPromise = null;
  let progressTimer = null;
  let seeking = false;

  const DEFAULT_PALETTE = {
    accent: '#FF1E10',
    accent_hover: '#FF4A3A',
    accent_deep: '#B40A00',
    accent_soft: 'rgba(255, 30, 16, 0.45)',
    accent_glow: 'rgba(255, 30, 16, 0.85)',
    bg_top: 'rgba(255, 30, 16, 0.55)',
    bg_side: 'rgba(180, 10, 0, 0.35)',
    aurora_1: '#FF6A55',
    aurora_2: '#FF1E10',
    aurora_3: '#8A0A00',
  };

  const MONO_BLACK = {
    accent: '#111111',
    accent_hover: '#2A2A2A',
    accent_deep: '#000000',
    accent_soft: 'rgba(0, 0, 0, 0.18)',
    accent_glow: 'rgba(0, 0, 0, 0.28)',
    bg_top: 'rgba(255, 255, 255, 0.95)',
    bg_side: 'rgba(230, 230, 230, 0.9)',
    aurora_1: '#FFFFFF',
    aurora_2: '#F0F0F0',
    aurora_3: '#D0D0D0',
    tone: 'black',
  };

  const MONO_WHITE = {
    accent: '#F5F5F5',
    accent_hover: '#FFFFFF',
    accent_deep: '#C8C8C8',
    accent_soft: 'rgba(255, 255, 255, 0.28)',
    accent_glow: 'rgba(255, 255, 255, 0.55)',
    bg_top: 'rgba(255, 255, 255, 0.55)',
    bg_side: 'rgba(230, 230, 230, 0.35)',
    aurora_1: '#FFFFFF',
    aurora_2: '#F4F4F4',
    aurora_3: '#D9D9D9',
    tone: 'white',
  };

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return '—';
    const total = Math.round(Number(seconds));
    if (!Number.isFinite(total) || total < 0) return '—';
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  function clamp(value, min = 0, max = 1) {
    return Math.min(max, Math.max(min, value));
  }

  function rgbToHex(r, g, b) {
    return `#${[r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('')}`.toUpperCase();
  }

  function rgbToHsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const d = max - min;
    let h = 0;
    if (d !== 0) {
      if (max === r) h = ((g - b) / d) % 6;
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h /= 6;
      if (h < 0) h += 1;
    }
    const s = max === 0 ? 0 : d / max;
    return [h, s, max];
  }

  function hsvToRgb(h, s, v) {
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);
    const table = [
      [v, t, p],
      [q, v, p],
      [p, v, t],
      [p, q, v],
      [t, p, v],
      [v, p, q],
    ];
    const [r, g, b] = table[i % 6];
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
  }

  function vividize(r, g, b) {
    let [h, s, v] = rgbToHsv(r, g, b);
    s = clamp(Math.max(s, 0.78) * 1.4, 0.82, 1);
    v = clamp(Math.max(v, 0.82), 0.78, 0.98);
    return hsvToRgb(h, s, v);
  }

  function paletteFromRgb(r, g, b) {
    const [ar, ag, ab] = vividize(r, g, b);
    const [h] = rgbToHsv(ar, ag, ab);
    const [lr, lg, lb] = hsvToRgb(h, 0.82, 0.98);
    const [dr, dg, db] = hsvToRgb(h, 0.95, 0.52);
    const [hr, hg, hb] = hsvToRgb(h, 0.9, 1);
    const [dbr, dbg, dbb] = hsvToRgb(h, 0.92, 0.46);

    return {
      accent: rgbToHex(ar, ag, ab),
      accent_hover: rgbToHex(hr, hg, hb),
      accent_deep: rgbToHex(dbr, dbg, dbb),
      accent_soft: `rgba(${ar}, ${ag}, ${ab}, 0.45)`,
      accent_glow: `rgba(${ar}, ${ag}, ${ab}, 0.85)`,
      bg_top: `rgba(${lr}, ${lg}, ${lb}, 0.55)`,
      bg_side: `rgba(${dr}, ${dg}, ${db}, 0.4)`,
      aurora_1: rgbToHex(lr, lg, lb),
      aurora_2: rgbToHex(ar, ag, ab),
      aurora_3: rgbToHex(dr, dg, db),
    };
  }

  function extractPaletteFromImage(img) {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, 64, 64);
    const { data } = ctx.getImageData(0, 0, 64, 64);
    const buckets = new Map();

    for (let i = 0; i < data.length; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      const [, s, v] = rgbToHsv(r, g, b);
      if (v < 0.14 || v > 0.97 || s < 0.12) continue;
      const key = `${r >> 4}_${g >> 4}_${b >> 4}`;
      const weight = (1 + s * 2.6) * (0.55 + Math.min(v, 0.9));
      const current = buckets.get(key) || { r, g, b, score: 0 };
      current.score += weight;
      buckets.set(key, current);
    }

    const ranked = [...buckets.values()].sort((a, b) => b.score - a.score).slice(0, 12);
    if (!ranked.length) return null;

    let best = ranked[0];
    let bestVivid = -1;
    for (const color of ranked) {
      const [, s, v] = rgbToHsv(color.r, color.g, color.b);
      const vivid = color.score * (0.35 + s) * (0.4 + v);
      if (vivid > bestVivid) {
        bestVivid = vivid;
        best = color;
      }
    }
    return paletteFromRgb(best.r, best.g, best.b);
  }

  function applyPalette(palette) {
    const colors = { ...DEFAULT_PALETTE, ...(palette || {}) };
    const root = document.documentElement;
    root.style.setProperty('--red', colors.accent);
    root.style.setProperty('--red-hover', colors.accent_hover);
    root.style.setProperty('--red-deep', colors.accent_deep);
    root.style.setProperty('--red-soft', colors.accent_soft);
    root.style.setProperty('--red-glow', colors.accent_glow);
    root.style.setProperty('--bg-top', colors.bg_top);
    root.style.setProperty('--bg-side', colors.bg_side);
    root.style.setProperty('--aurora-1', colors.aurora_1);
    root.style.setProperty('--aurora-2', colors.aurora_2);
    root.style.setProperty('--aurora-3', colors.aurora_3);
    document.body.classList.add('themed');
    document.body.classList.toggle('cover-black', colors.tone === 'black');
    document.body.classList.toggle('cover-white', colors.tone === 'white');
  }

  function resetPalette() {
    applyPalette({ ...DEFAULT_PALETTE, tone: 'color' });
    document.body.classList.remove('themed', 'cover-black', 'cover-white');
  }

  function coverSrc(thumbnail) {
    if (!thumbnail) return '';
    return `/api/cover?src=${encodeURIComponent(thumbnail)}`;
  }

  function setSearchLoading(loading) {
    searchBtn.disabled = loading;
    searchBtn.textContent = loading ? 'Cargando…' : 'Vista previa';
  }

  function showError(message) {
    searchError.textContent = message;
    searchError.hidden = false;
  }

  function clearError() {
    searchError.hidden = true;
    searchError.textContent = '';
  }

  function selectedFormat() {
    const checked = document.querySelector('input[name="format"]:checked');
    return checked ? checked.value : 'mp3';
  }

  function updateFormatUI() {
    const format = selectedFormat();
    previewFormatLabel.textContent = format.toUpperCase();
    formatNote.hidden = format !== 'wav';
  }

  formatInputs.forEach((input) => input.addEventListener('change', updateFormatUI));

  function loadYouTubeApi() {
    if (window.YT && window.YT.Player) return Promise.resolve();
    if (ytApiPromise) return ytApiPromise;

    ytApiPromise = new Promise((resolve) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        if (typeof previous === 'function') previous();
        resolve();
      };
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      document.head.appendChild(script);
    });

    return ytApiPromise;
  }

  function setPlayingUi(playing) {
    playIcon.hidden = playing;
    pauseIcon.hidden = !playing;
    playBtn.setAttribute('aria-label', playing ? 'Pausar' : 'Reproducir');
    coverStage.classList.toggle('is-playing', playing);
  }

  function setPlayerMessage(message) {
    if (!message) {
      playerStatus.hidden = true;
      playerStatus.textContent = '';
      return;
    }
    playerStatus.hidden = false;
    playerStatus.textContent = message;
  }

  function stopProgress() {
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  function updateProgress() {
    if (!ytPlayer || seeking || typeof ytPlayer.getCurrentTime !== 'function') return;
    const duration = ytPlayer.getDuration() || 0;
    const current = ytPlayer.getCurrentTime() || 0;
    if (duration > 0) {
      seekBar.max = String(duration);
      seekBar.value = String(current);
      timeTotal.textContent = formatDuration(duration);
    }
    timeCurrent.textContent = formatDuration(current);
  }

  function startProgress() {
    stopProgress();
    updateProgress();
    progressTimer = setInterval(updateProgress, 400);
  }

  function destroyPlayer() {
    stopProgress();
    setPlayingUi(false);
    if (ytPlayer && typeof ytPlayer.destroy === 'function') {
      try {
        ytPlayer.destroy();
      } catch (_error) {
        /* ignore */
      }
    }
    ytPlayer = null;
    ytReady = false;
    seekBar.value = '0';
    timeCurrent.textContent = '0:00';

    if (!document.getElementById('yt-player')) {
      const fresh = document.createElement('div');
      fresh.id = 'yt-player';
      fresh.className = 'yt-player';
      document.querySelector('.player-panel').prepend(fresh);
    }
  }

  function ensurePlayer() {
    if (ytPlayer) return Promise.resolve(ytPlayer);
    return loadYouTubeApi().then(() => new Promise((resolve, reject) => {
      ytPlayer = new window.YT.Player('yt-player', {
        height: '1',
        width: '1',
        videoId: currentVideoId,
        playerVars: {
          autoplay: 0,
          controls: 0,
          disablekb: 1,
          fs: 0,
          modestbranding: 1,
          playsinline: 1,
          rel: 0,
        },
        events: {
          onReady: (event) => {
            ytReady = true;
            const duration = event.target.getDuration() || 0;
            seekBar.max = String(duration || 100);
            timeTotal.textContent = formatDuration(duration);
            resolve(event.target);
          },
          onStateChange: (event) => {
            const playing = event.data === window.YT.PlayerState.PLAYING;
            setPlayingUi(playing);
            if (playing) {
              setPlayerMessage('');
              startProgress();
            } else {
              stopProgress();
              updateProgress();
            }
            if (event.data === window.YT.PlayerState.ENDED) {
              setPlayingUi(false);
              seekBar.value = '0';
              timeCurrent.textContent = '0:00';
            }
          },
          onError: () => {
            setPlayingUi(false);
            setPlayerMessage('YouTube bloqueó la reproducción aquí. Prueba abrir el video en YouTube o descarga el audio.');
            reject(new Error('No se pudo reproducir este video.'));
          },
        },
      });
    }));
  }

  async function togglePlayback() {
    if (!currentVideoId) return;
    playBtn.disabled = true;
    setPlayerMessage('');
    try {
      const player = await ensurePlayer();
      const state = player.getPlayerState();
      if (state === window.YT.PlayerState.PLAYING) {
        player.pauseVideo();
      } else {
        player.playVideo();
      }
    } catch (error) {
      setPlayerMessage(error.message || 'No se pudo reproducir este video.');
    } finally {
      playBtn.disabled = false;
    }
  }

  playBtn.addEventListener('click', togglePlayback);

  seekBar.addEventListener('input', () => {
    seeking = true;
    timeCurrent.textContent = formatDuration(Number(seekBar.value));
  });

  seekBar.addEventListener('change', () => {
    seeking = false;
    if (ytPlayer && ytReady && typeof ytPlayer.seekTo === 'function') {
      ytPlayer.seekTo(Number(seekBar.value), true);
    }
  });

  function detectCoverTone(img) {
    const probe = document.createElement('canvas');
    probe.width = 32;
    probe.height = 32;
    const ctx = probe.getContext('2d', { willReadFrequently: true });
    if (!ctx) return 'color';
    ctx.drawImage(img, 0, 0, 32, 32);
    const { data } = ctx.getImageData(0, 0, 32, 32);
    let sat = 0;
    let val = 0;
    const count = data.length / 4;
    for (let i = 0; i < data.length; i += 4) {
      const [, s, v] = rgbToHsv(data[i], data[i + 1], data[i + 2]);
      sat += s;
      val += v;
    }
    sat /= count;
    val /= count;
    if (sat < 0.16) {
      if (val < 0.34) return 'black';
      if (val > 0.72) return 'white';
    }
    return 'color';
  }

  previewThumb.addEventListener('load', () => {
    const tone = detectCoverTone(previewThumb);
    if (tone === 'black') {
      applyPalette(MONO_BLACK);
      return;
    }
    if (tone === 'white') {
      applyPalette(MONO_WHITE);
      return;
    }
    const extracted = extractPaletteFromImage(previewThumb);
    if (extracted) applyPalette(extracted);
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    clearError();
    setSearchLoading(true);
    preview.hidden = true;
    downloadStatus.hidden = true;
    destroyPlayer();
    setPlayerMessage('');

    try {
      const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'No pudimos leer ese enlace.');
      }

      currentUrl = url;
      currentVideoId = data.id || '';
      applyPalette(data.palette);
      previewThumb.src = coverSrc(data.thumbnail);
      previewThumb.alt = data.title ? `Portada de ${data.title}` : 'Portada';
      previewTitle.textContent = data.title || 'Sin título';
      previewArtist.textContent = data.uploader || 'Artista desconocido';
      previewDuration.textContent = formatDuration(data.duration);
      timeTotal.textContent = formatDuration(data.duration);
      timeCurrent.textContent = '0:00';
      seekBar.value = '0';
      playerNow.textContent = data.title
        ? `${data.title}${data.uploader ? ` — ${data.uploader}` : ''}`
        : 'Listo para reproducir';
      playBtn.disabled = !currentVideoId;

      preview.hidden = false;
      updateFormatUI();
    } catch (error) {
      resetPalette();
      showError(
        error.message ||
          'No pudimos leer ese enlace. Verifica que sea un enlace válido de YouTube o YouTube Music.'
      );
    } finally {
      setSearchLoading(false);
    }
  });

  downloadBtn.addEventListener('click', async () => {
    if (!currentUrl) return;
    const format = selectedFormat();

    downloadBtn.disabled = true;
    downloadBtn.classList.add('loading');
    downloadBtnLabel.textContent = 'Descargando…';
    downloadStatus.hidden = true;

    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: currentUrl, format }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'No se pudo completar la descarga.');
      }

      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `audio.${format}`;

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);

      downloadStatus.textContent =
        format === 'wav'
          ? 'Descarga completa.'
          : 'Descarga completa, con portada incluida.';
      downloadStatus.hidden = false;
    } catch (error) {
      downloadStatus.textContent = error.message || 'No se pudo completar la descarga.';
      downloadStatus.hidden = false;
    } finally {
      downloadBtn.disabled = false;
      downloadBtn.classList.remove('loading');
      downloadBtnLabel.textContent = 'Descargar';
    }
  });
})();
