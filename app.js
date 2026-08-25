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

  const formatInputs =
    document.querySelectorAll('input[name="format"]');

  const formatNote =
    document.getElementById('format-note');

  const downloadBtn =
    document.getElementById('download-btn');

  const downloadBtnLabel =
    downloadBtn.querySelector('.download-btn-label');

  const downloadStatus =
    document.getElementById('download-status');

  const coverStage =
    document.querySelector('.cover-stage');

  const playBtn =
    document.getElementById('play-btn');

  const playIcon =
    document.getElementById('play-icon');

  const pauseIcon =
    document.getElementById('pause-icon');

  const seekBar =
    document.getElementById('seek-bar');

  const timeCurrent =
    document.getElementById('time-current');

  const timeTotal =
    document.getElementById('time-total');

  const playerNow =
    document.getElementById('player-now');

  const playerStatus =
    document.getElementById('player-status');


  /* =========================================
     DESCARGA
     ========================================= */

  const downloadOverlay =
    document.getElementById('download-overlay');

  const downloadModalTitle =
    document.getElementById('download-modal-title');

  const downloadPercent =
    document.getElementById('download-percent');

  const downloadSize =
    document.getElementById('download-size');

  const downloadProgressBar =
    document.getElementById('download-progress-bar');

  const downloadSpeed =
    document.getElementById('download-speed');

  const downloadEta =
    document.getElementById('download-eta');

  const cancelDownloadBtn =
    document.getElementById('cancel-download-btn');


  /* =========================================
     HISTORIAL
     ========================================= */

  const downloadHistory =
    document.getElementById('download-history');

  const emptyHistory =
    document.getElementById('empty-history');

  const downloadCount =
    document.getElementById('download-count');

  const currentFormat =
    document.getElementById('current-format');


  let downloadedSongs = 0;

  let downloadController = null;

  let currentUrl = '';
  let currentVideoId = '';

  let currentTitle = '';
  let currentArtist = '';

  let ytPlayer = null;
  let ytReady = false;
  let ytApiPromise = null;
  let progressTimer = null;
  let seeking = false;


  /* =========================================
     PALETAS
     ========================================= */

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
    aurora_3: '#8A0A00'
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
    tone: 'black'
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
    tone: 'white'
  };


  /* =========================================
     FUNCIONES GENERALES
     ========================================= */

  function formatDuration(seconds) {

    if (
      seconds === null ||
      seconds === undefined
    ) {
      return '—';
    }

    const total =
      Math.round(Number(seconds));

    if (
      !Number.isFinite(total) ||
      total < 0
    ) {
      return '—';
    }

    const hours =
      Math.floor(total / 3600);

    const minutes =
      Math.floor((total % 3600) / 60);

    const secs =
      total % 60;

    if (hours > 0) {

      return `${hours}:${minutes
        .toString()
        .padStart(2, '0')}:${secs
        .toString()
        .padStart(2, '0')}`;

    }

    return `${minutes}:${secs
      .toString()
      .padStart(2, '0')}`;
  }


  function clamp(
    value,
    min = 0,
    max = 1
  ) {

    return Math.min(
      max,
      Math.max(min, value)
    );
  }


  function rgbToHex(r, g, b) {

    return `#${[
      r,
      g,
      b
    ]
      .map(n =>
        n.toString(16).padStart(2, '0')
      )
      .join('')
    }`.toUpperCase();
  }


  function rgbToHsv(r, g, b) {

    r /= 255;
    g /= 255;
    b /= 255;

    const max =
      Math.max(r, g, b);

    const min =
      Math.min(r, g, b);

    const d =
      max - min;

    let h = 0;

    if (d !== 0) {

      if (max === r) {
        h = ((g - b) / d) % 6;
      } else if (max === g) {
        h = (b - r) / d + 2;
      } else {
        h = (r - g) / d + 4;
      }

      h /= 6;

      if (h < 0) {
        h += 1;
      }
    }

    const s =
      max === 0 ? 0 : d / max;

    return [h, s, max];
  }


  function hsvToRgb(h, s, v) {

    const i =
      Math.floor(h * 6);

    const f =
      h * 6 - i;

    const p =
      v * (1 - s);

    const q =
      v * (1 - f * s);

    const t =
      v * (1 - (1 - f) * s);

    const table = [
      [v, t, p],
      [q, v, p],
      [p, v, t],
      [p, q, v],
      [t, p, v],
      [v, p, q]
    ];

    const [r, g, b] =
      table[i % 6];

    return [
      Math.round(r * 255),
      Math.round(g * 255),
      Math.round(b * 255)
    ];
  }


  function vividize(r, g, b) {

    let [h, s, v] =
      rgbToHsv(r, g, b);

    s =
      clamp(
        Math.max(s, 0.78) * 1.4,
        0.82,
        1
      );

    v =
      clamp(
        Math.max(v, 0.82),
        0.78,
        0.98
      );

    return hsvToRgb(h, s, v);
  }


  function paletteFromRgb(r, g, b) {

    const [ar, ag, ab] =
      vividize(r, g, b);

    const [h] =
      rgbToHsv(ar, ag, ab);

    const [lr, lg, lb] =
      hsvToRgb(h, 0.82, 0.98);

    const [dr, dg, db] =
      hsvToRgb(h, 0.95, 0.52);

    const [hr, hg, hb] =
      hsvToRgb(h, 0.9, 1);

    const [dbr, dbg, dbb] =
      hsvToRgb(h, 0.92, 0.46);

    return {

      accent:
        rgbToHex(ar, ag, ab),

      accent_hover:
        rgbToHex(hr, hg, hb),

      accent_deep:
        rgbToHex(dbr, dbg, dbb),

      accent_soft:
        `rgba(${ar}, ${ag}, ${ab}, 0.45)`,

      accent_glow:
        `rgba(${ar}, ${ag}, ${ab}, 0.85)`,

      bg_top:
        `rgba(${lr}, ${lg}, ${lb}, 0.55)`,

      bg_side:
        `rgba(${dr}, ${dg}, ${db}, 0.4)`,

      aurora_1:
        rgbToHex(lr, lg, lb),

      aurora_2:
        rgbToHex(ar, ag, ab),

      aurora_3:
        rgbToHex(dr, dg, db)
    };
  }


  function extractPaletteFromImage(img) {

    const canvas =
      document.createElement('canvas');

    canvas.width = 64;
    canvas.height = 64;

    const ctx =
      canvas.getContext(
        '2d',
        {
          willReadFrequently: true
        }
      );

    if (!ctx) {
      return null;
    }

    ctx.drawImage(
      img,
      0,
      0,
      64,
      64
    );

    const { data } =
      ctx.getImageData(
        0,
        0,
        64,
        64
      );

    const buckets =
      new Map();

    for (
      let i = 0;
      i < data.length;
      i += 4
    ) {

      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];

      const [, s, v] =
        rgbToHsv(r, g, b);

      if (
        v < 0.14 ||
        v > 0.97 ||
        s < 0.12
      ) {
        continue;
      }

      const key =
        `${r >> 4}_${g >> 4}_${b >> 4}`;

      const weight =
        (1 + s * 2.6) *
        (0.55 + Math.min(v, 0.9));

      const current =
        buckets.get(key) ||
        {
          r,
          g,
          b,
          score: 0
        };

      current.score += weight;

      buckets.set(
        key,
        current
      );
    }

    const ranked =
      [...buckets.values()]
        .sort(
          (a, b) =>
            b.score - a.score
        )
        .slice(0, 12);

    if (!ranked.length) {
      return null;
    }

    let best =
      ranked[0];

    let bestVivid = -1;

    for (const color of ranked) {

      const [, s, v] =
        rgbToHsv(
          color.r,
          color.g,
          color.b
        );

      const vivid =
        color.score *
        (0.35 + s) *
        (0.4 + v);

      if (vivid > bestVivid) {

        bestVivid = vivid;
        best = color;

      }
    }

    return paletteFromRgb(
      best.r,
      best.g,
      best.b
    );
  }


  function applyPalette(palette) {

    const colors = {
      ...DEFAULT_PALETTE,
      ...(palette || {})
    };

    const root =
      document.documentElement;

    root.style.setProperty(
      '--red',
      colors.accent
    );

    root.style.setProperty(
      '--red-hover',
      colors.accent_hover
    );

    root.style.setProperty(
      '--red-deep',
      colors.accent_deep
    );

    root.style.setProperty(
      '--red-soft',
      colors.accent_soft
    );

    root.style.setProperty(
      '--red-glow',
      colors.accent_glow
    );

    root.style.setProperty(
      '--bg-top',
      colors.bg_top
    );

    root.style.setProperty(
      '--bg-side',
      colors.bg_side
    );

    root.style.setProperty(
      '--aurora-1',
      colors.aurora_1
    );

    root.style.setProperty(
      '--aurora-2',
      colors.aurora_2
    );

    root.style.setProperty(
      '--aurora-3',
      colors.aurora_3
    );

    document.body.classList.add('themed');

    document.body.classList.toggle(
      'cover-black',
      colors.tone === 'black'
    );

    document.body.classList.toggle(
      'cover-white',
      colors.tone === 'white'
    );
  }


  function resetPalette() {

    applyPalette({
      ...DEFAULT_PALETTE,
      tone: 'color'
    });

    document.body.classList.remove(
      'themed',
      'cover-black',
      'cover-white'
    );
  }


  function coverSrc(thumbnail) {

    if (!thumbnail) {
      return '';
    }

    return `/api/cover?src=${encodeURIComponent(thumbnail)}`;
  }


  function formatBytes(bytes) {

    if (
      !Number.isFinite(bytes) ||
      bytes <= 0
    ) {
      return '—';
    }

    const units = [
      'B',
      'KB',
      'MB',
      'GB'
    ];

    let value = bytes;
    let unit = 0;

    while (
      value >= 1024 &&
      unit < units.length - 1
    ) {

      value /= 1024;
      unit++;
    }

    return `${value.toFixed(
      unit === 0 ? 0 : 1
    )} ${units[unit]}`;
  }


  function formatEta(seconds) {

    if (
      !Number.isFinite(seconds) ||
      seconds < 0
    ) {
      return '—';
    }

    const total =
      Math.round(seconds);

    const minutes =
      Math.floor(total / 60);

    const secs =
      total % 60;

    if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    }

    return `${secs}s`;
  }


  /* =========================================
     DESCARGA
     ========================================= */

  function openDownloadModal() {

    downloadOverlay.hidden = false;

    downloadModalTitle.textContent =
      currentTitle ||
      'Preparando canción...';

    downloadPercent.textContent =
      'Preparando';

    downloadSize.textContent =
      'Procesando audio...';

    downloadProgressBar.style.width =
      '2%';

    downloadSpeed.textContent =
      '⚡ Preparando';

    downloadEta.textContent =
      '⏱ Calculando';
  }


  function closeDownloadModal() {

    downloadOverlay.hidden = true;
  }


  function updateDownloadProgress(
    percent,
    downloaded,
    total,
    speed,
    eta
  ) {

    let safePercent =
      Number(percent);

    if (!Number.isFinite(safePercent)) {
      safePercent = 0;
    }

    safePercent =
      Math.min(
        100,
        Math.max(
          0,
          safePercent
        )
      );


    downloadPercent.textContent =
      `${safePercent.toFixed(0)}%`;

    downloadProgressBar.style.width =
      `${safePercent}%`;


    if (total > 0) {

      downloadSize.textContent =
        `${formatBytes(downloaded)} / ${formatBytes(total)}`;

    } else {

      downloadSize.textContent =
        formatBytes(downloaded);

    }


    downloadSpeed.textContent =
      speed > 0
        ? `⚡ ${formatBytes(speed)}/s`
        : '⚡ Procesando';


    downloadEta.textContent =
      eta !== null &&
      eta !== undefined
        ? `⏱ ${formatEta(eta)}`
        : '⏱ Calculando';
  }


  function setSearchLoading(loading) {

    searchBtn.disabled =
      loading;

    searchBtn.textContent =
      loading
        ? 'Cargando…'
        : 'Vista previa';
  }


  function showError(message) {

    searchError.textContent =
      message;

    searchError.hidden =
      false;
  }


  function clearError() {

    searchError.hidden =
      true;

    searchError.textContent =
      '';
  }


  function selectedFormat() {

    const checked =
      document.querySelector(
        'input[name="format"]:checked'
      );

    return checked
      ? checked.value
      : 'mp3';
  }


  function updateFormatUI() {

    const format =
      selectedFormat();

    previewFormatLabel.textContent =
      format.toUpperCase();

    formatNote.hidden =
      format !== 'wav';

    currentFormat.textContent =
      format.toUpperCase();
  }


  formatInputs.forEach(
    input =>
      input.addEventListener(
        'change',
        updateFormatUI
      )
  );


  /* =========================================
     AGREGAR CANCIÓN A LA LISTA
     ========================================= */

  function addDownloadedSong(
    title,
    artist,
    format
  ) {

    downloadedSongs++;

    downloadCount.textContent =
      downloadedSongs;


    if (emptyHistory) {
      emptyHistory.remove();
    }


    const item =
      document.createElement('div');

    item.className =
      'history-item';


    const number =
      document.createElement('div');

    number.className =
      'history-number';

    number.textContent =
      downloadedSongs;


    const music =
      document.createElement('div');

    music.className =
      'history-music';


    const titleElement =
      document.createElement('div');

    titleElement.className =
      'history-title';

    titleElement.textContent =
      title || 'Canción';


    const artistElement =
      document.createElement('div');

    artistElement.className =
      'history-artist';

    artistElement.textContent =
      artist || 'Artista desconocido';


    const formatElement =
      document.createElement('span');

    formatElement.className =
      'history-format';

    formatElement.textContent =
      format.toUpperCase();


    music.appendChild(
      titleElement
    );

    music.appendChild(
      artistElement
    );

    item.appendChild(
      number
    );

    item.appendChild(
      music
    );

    item.appendChild(
      formatElement
    );


    downloadHistory.prepend(
      item
    );
  }


  /* =========================================
     YOUTUBE API
     ========================================= */

  function loadYouTubeApi() {

    if (
      window.YT &&
      window.YT.Player
    ) {
      return Promise.resolve();
    }

    if (ytApiPromise) {
      return ytApiPromise;
    }

    ytApiPromise =
      new Promise(resolve => {

        const previous =
          window.onYouTubeIframeAPIReady;

        window.onYouTubeIframeAPIReady =
          () => {

            if (
              typeof previous ===
              'function'
            ) {
              previous();
            }

            resolve();
          };


        const script =
          document.createElement(
            'script'
          );

        script.src =
          'https://www.youtube.com/iframe_api';

        document.head.appendChild(
          script
        );
      });

    return ytApiPromise;
  }


  function setPlayingUi(playing) {

    playIcon.hidden =
      playing;

    pauseIcon.hidden =
      !playing;

    playBtn.setAttribute(
      'aria-label',
      playing
        ? 'Pausar'
        : 'Reproducir'
    );

    coverStage.classList.toggle(
      'is-playing',
      playing
    );
  }


  function setPlayerMessage(message) {

    if (!message) {

      playerStatus.hidden =
        true;

      playerStatus.textContent =
        '';

      return;
    }

    playerStatus.hidden =
      false;

    playerStatus.textContent =
      message;
  }


  function stopProgress() {

    if (progressTimer) {

      clearInterval(
        progressTimer
      );

      progressTimer =
        null;
    }
  }


  function updateProgress() {

    if (
      !ytPlayer ||
      seeking ||
      typeof ytPlayer.getCurrentTime !==
        'function'
    ) {
      return;
    }

    const duration =
      ytPlayer.getDuration() || 0;

    const current =
      ytPlayer.getCurrentTime() || 0;

    if (duration > 0) {

      seekBar.max =
        String(duration);

      seekBar.value =
        String(current);

      timeTotal.textContent =
        formatDuration(duration);
    }

    timeCurrent.textContent =
      formatDuration(current);
  }


  function startProgress() {

    stopProgress();

    updateProgress();

    progressTimer =
      setInterval(
        updateProgress,
        400
      );
  }


  function destroyPlayer() {

    stopProgress();

    setPlayingUi(false);

    if (
      ytPlayer &&
      typeof ytPlayer.destroy ===
        'function'
    ) {

      try {
        ytPlayer.destroy();
      } catch (_) {}
    }

    ytPlayer =
      null;

    ytReady =
      false;

    seekBar.value =
      '0';

    timeCurrent.textContent =
      '0:00';


    if (
      !document.getElementById(
        'yt-player'
      )
    ) {

      const fresh =
        document.createElement(
          'div'
        );

      fresh.id =
        'yt-player';

      fresh.className =
        'yt-player';

      document
        .querySelector(
          '.player-panel'
        )
        .prepend(fresh);
    }
  }


  function ensurePlayer() {

    if (ytPlayer) {
      return Promise.resolve(
        ytPlayer
      );
    }

    return loadYouTubeApi()
      .then(
        () =>
          new Promise(
            (resolve, reject) => {

              ytPlayer =
                new window.YT.Player(
                  'yt-player',
                  {

                    height: '1',
                    width: '1',

                    videoId:
                      currentVideoId,

                    playerVars: {

                      autoplay: 0,
                      controls: 0,
                      disablekb: 1,
                      fs: 0,
                      modestbranding: 1,
                      playsinline: 1,
                      rel: 0
                    },

                    events: {

                      onReady:
                        event => {

                          ytReady =
                            true;

                          const duration =
                            event.target
                              .getDuration() || 0;

                          seekBar.max =
                            String(
                              duration || 100
                            );

                          timeTotal.textContent =
                            formatDuration(
                              duration
                            );

                          resolve(
                            event.target
                          );
                        },


                      onStateChange:
                        event => {

                          const playing =
                            event.data ===
                            window.YT
                              .PlayerState
                              .PLAYING;

                          setPlayingUi(
                            playing
                          );

                          if (playing) {

                            setPlayerMessage(
                              ''
                            );

                            startProgress();

                          } else {

                            stopProgress();

                            updateProgress();
                          }


                          if (
                            event.data ===
                            window.YT
                              .PlayerState
                              .ENDED
                          ) {

                            setPlayingUi(
                              false
                            );

                            seekBar.value =
                              '0';

                            timeCurrent.textContent =
                              '0:00';
                          }
                        },


                      onError:
                        () => {

                          setPlayingUi(
                            false
                          );

                          setPlayerMessage(
                            'YouTube bloqueó la reproducción aquí.'
                          );

                          reject(
                            new Error(
                              'No se pudo reproducir este video.'
                            )
                          );
                        }
                    }
                  }
                );
            }
          )
      );
  }


  async function togglePlayback() {

    if (!currentVideoId) {
      return;
    }

    playBtn.disabled =
      true;

    setPlayerMessage('');

    try {

      const player =
        await ensurePlayer();

      const state =
        player.getPlayerState();

      if (
        state ===
        window.YT.PlayerState.PLAYING
      ) {

        player.pauseVideo();

      } else {

        player.playVideo();
      }

    } catch (error) {

      setPlayerMessage(
        error.message ||
        'No se pudo reproducir este video.'
      );

    } finally {

      playBtn.disabled =
        false;
    }
  }


  playBtn.addEventListener(
    'click',
    togglePlayback
  );


  seekBar.addEventListener(
    'input',
    () => {

      seeking = true;

      timeCurrent.textContent =
        formatDuration(
          Number(
            seekBar.value
          )
        );
    }
  );


  seekBar.addEventListener(
    'change',
    () => {

      seeking = false;

      if (
        ytPlayer &&
        ytReady &&
        typeof ytPlayer.seekTo ===
          'function'
      ) {

        ytPlayer.seekTo(
          Number(
            seekBar.value
          ),
          true
        );
      }
    }
  );


  /* =========================================
     PORTADA / COLOR
     ========================================= */

  function detectCoverTone(img) {

    const probe =
      document.createElement(
        'canvas'
      );

    probe.width = 32;
    probe.height = 32;

    const ctx =
      probe.getContext(
        '2d',
        {
          willReadFrequently: true
        }
      );

    if (!ctx) {
      return 'color';
    }

    ctx.drawImage(
      img,
      0,
      0,
      32,
      32
    );

    const { data } =
      ctx.getImageData(
        0,
        0,
        32,
        32
      );

    let sat = 0;
    let val = 0;

    const count =
      data.length / 4;

    for (
      let i = 0;
      i < data.length;
      i += 4
    ) {

      const [, s, v] =
        rgbToHsv(
          data[i],
          data[i + 1],
          data[i + 2]
        );

      sat += s;
      val += v;
    }

    sat /= count;
    val /= count;

    if (sat < 0.16) {

      if (val < 0.34) {
        return 'black';
      }

      if (val > 0.72) {
        return 'white';
      }
    }

    return 'color';
  }


  previewThumb.addEventListener(
    'load',
    () => {

      const tone =
        detectCoverTone(
          previewThumb
        );

      if (tone === 'black') {

        applyPalette(
          MONO_BLACK
        );

        return;
      }

      if (tone === 'white') {

        applyPalette(
          MONO_WHITE
        );

        return;
      }

      const extracted =
        extractPaletteFromImage(
          previewThumb
        );

      if (extracted) {
        applyPalette(
          extracted
        );
      }
    }
  );


  /* =========================================
     BÚSQUEDA
     ========================================= */

  form.addEventListener(
    'submit',
    async event => {

      event.preventDefault();

      const url =
        urlInput.value.trim();

      if (!url) {
        return;
      }

      clearError();

      setSearchLoading(
        true
      );

      preview.hidden =
        true;

      downloadStatus.hidden =
        true;

      destroyPlayer();

      setPlayerMessage('');

      try {

        const response =
          await fetch(
            `/api/info?url=${encodeURIComponent(url)}`
          );

        const data =
          await response.json();

        if (!response.ok) {

          throw new Error(
            data.detail ||
            'No pudimos leer ese enlace.'
          );
        }


        currentUrl =
          url;

        currentVideoId =
          data.id || '';

        currentTitle =
          data.title ||
          'Sin título';

        currentArtist =
          data.uploader ||
          'Artista desconocido';


        applyPalette(
          data.palette
        );


        previewThumb.src =
          coverSrc(
            data.thumbnail
          );

        previewThumb.alt =
          data.title
            ? `Portada de ${data.title}`
            : 'Portada';


        previewTitle.textContent =
          currentTitle;

        previewArtist.textContent =
          currentArtist;

        previewDuration.textContent =
          formatDuration(
            data.duration
          );

        timeTotal.textContent =
          formatDuration(
            data.duration
          );

        timeCurrent.textContent =
          '0:00';

        seekBar.value =
          '0';


        playerNow.textContent =
          data.title
            ? `${data.title}${
                data.uploader
                  ? ` — ${data.uploader}`
                  : ''
              }`
            : 'Listo para reproducir';


        playBtn.disabled =
          !currentVideoId;


        preview.hidden =
          false;

        updateFormatUI();

      } catch (error) {

        resetPalette();

        showError(
          error.message ||
          'No pudimos leer ese enlace.'
        );

      } finally {

        setSearchLoading(
          false
        );
      }
    }
  );


  /* =========================================
     DESCARGA
     ========================================= */

  downloadBtn.addEventListener(
    'click',
    async () => {

      if (!currentUrl) {
        return;
      }


      const format =
        selectedFormat();


      downloadBtn.disabled =
        true;

      downloadBtn.classList.add(
        'loading'
      );

      downloadBtnLabel.textContent =
        'Descargando…';

      downloadStatus.hidden =
        true;


      openDownloadModal();


      downloadController =
        new AbortController();


      try {

        const response =
          await fetch(
            '/api/download',
            {

              method: 'POST',

              headers: {
                'Content-Type':
                  'application/json'
              },

              body:
                JSON.stringify({
                  url: currentUrl,
                  format
                }),

              signal:
                downloadController.signal
            }
          );


        if (!response.ok) {

          const data =
            await response
              .json()
              .catch(
                () => ({})
              );

          throw new Error(
            data.detail ||
            'No se pudo completar la descarga.'
          );
        }


        const total =
          Number(
            response.headers.get(
              'Content-Length'
            )
          ) || 0;


        const disposition =
          response.headers.get(
            'Content-Disposition'
          ) || '';


        let filename =
          `audio.${format}`;


        /*
         * Usamos el nombre enviado
         * por el servidor.
         *
         * Si el servidor ya genera:
         *
         * Cancion - Artista.mp3
         *
         * se conservará ese nombre.
         */

        const utf8Match =
          disposition.match(
            /filename\*=UTF-8''([^;]+)/i
          );

        const normalMatch =
          disposition.match(
            /filename="?([^"]+)"?/i
          );


        if (utf8Match) {

          try {

            filename =
              decodeURIComponent(
                utf8Match[1]
              );

          } catch (_) {

            filename =
              utf8Match[1];
          }

        } else if (normalMatch) {

          filename =
            normalMatch[1];
        }


        if (!response.body) {

          throw new Error(
            'El navegador no permite mostrar el progreso.'
          );
        }


        const reader =
          response.body.getReader();


        const chunks = [];

        let received = 0;

        const startTime =
          performance.now();


        /*
         * Mostrar progreso inmediatamente.
         */

        updateDownloadProgress(
          3,
          0,
          total,
          0,
          null
        );


        while (true) {

          const {
            done,
            value
          } =
            await reader.read();


          if (done) {
            break;
          }


          chunks.push(
            value
          );

          received +=
            value.length;


          const elapsed =
            (
              performance.now() -
              startTime
            ) / 1000;


          const speed =
            elapsed > 0
              ? received / elapsed
              : 0;


          let percent =
            total > 0
              ? (
                  received /
                  total
                ) * 100
              : 0;


          /*
           * Evitamos que visualmente
           * parezca congelado al 0%.
           */

          if (
            percent < 3 &&
            received > 0
          ) {
            percent = 3;
          }


          const remaining =
            total > 0 &&
            speed > 0
              ? (
                  total -
                  received
                ) / speed
              : null;


          updateDownloadProgress(
            percent,
            received,
            total,
            speed,
            remaining
          );
        }


        updateDownloadProgress(
          100,
          received,
          total,
          0,
          0
        );


        const blob =
          new Blob(
            chunks
          );


        const objectUrl =
          URL.createObjectURL(
            blob
          );


        const link =
          document.createElement(
            'a'
          );


        link.href =
          objectUrl;

        link.download =
          filename;


        document.body.appendChild(
          link
        );

        link.click();

        link.remove();


        URL.revokeObjectURL(
          objectUrl
        );


        /*
         * AGREGAR A LA LISTA
         */

        addDownloadedSong(
          currentTitle,
          currentArtist,
          format
        );


        downloadStatus.textContent =
          'Descarga completa.';

        downloadStatus.hidden =
          false;


        /*
         * Dejamos el recuadro
         * visible un momento
         * mostrando 100%.
         */

        setTimeout(
          () => {

            closeDownloadModal();

          },
          700
        );


      } catch (error) {

        if (
          error.name ===
          'AbortError'
        ) {

          downloadStatus.textContent =
            'Descarga cancelada.';

        } else {

          downloadStatus.textContent =
            error.message ||
            'No se pudo completar la descarga.';
        }


        downloadStatus.hidden =
          false;


        closeDownloadModal();


      } finally {

        downloadController =
          null;

        downloadBtn.disabled =
          false;

        downloadBtn.classList.remove(
          'loading'
        );

        downloadBtnLabel.textContent =
          'Descargar';
      }
    }
  );


  cancelDownloadBtn.addEventListener(
    'click',
    () => {

      if (downloadController) {

        downloadController.abort();

      }
    }
  );


  /*
   * Estado inicial
   */

  updateFormatUI();

})();
