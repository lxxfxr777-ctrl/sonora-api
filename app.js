```javascript
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

  /* =========================================================
     RESPONSIVE / ESTABILIDAD VISUAL
     ========================================================= */

  function installResponsiveLayout() {
    if (document.getElementById('app-responsive-fix')) {
      return;
    }

    const style = document.createElement('style');

    style.id = 'app-responsive-fix';

    style.textContent = `
      /* =====================================================
         ESTABILIDAD GENERAL
         ===================================================== */

      html {
        width: 100%;
        min-width: 0;
        overflow-x: hidden;
        scrollbar-gutter: stable;
      }

      body {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        overflow-x: hidden;
        box-sizing: border-box;
      }

      *,
      *::before,
      *::after {
        box-sizing: border-box;
      }

      img,
      video,
      iframe,
      canvas {
        max-width: 100%;
      }

      button,
      input,
      select,
      textarea {
        max-width: 100%;
      }

      /* =====================================================
         CONTENEDORES
         ===================================================== */

      .container,
      .page,
      .main,
      main,
      .app,
      .app-container,
      .content,
      .main-content {
        min-width: 0;
        max-width: 100%;
      }

      /* =====================================================
         FORMULARIO DE BÚSQUEDA
         ===================================================== */

      #search-form {
        width: 100%;
        min-width: 0;
        max-width: 100%;
      }

      #url-input {
        min-width: 0;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
      }

      #search-btn {
        flex-shrink: 0;
      }

      /* =====================================================
         VISTA PREVIA
         ===================================================== */

      #preview {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
      }

      #preview:not([hidden]) {
        width: 100%;
        max-width: 100%;
      }

      #preview-thumb {
        display: block;
        max-width: 100%;
        width: 100%;
        height: auto;
        object-fit: cover;
      }

      .preview,
      .preview-card,
      .preview-content,
      .preview-info,
      .preview-details,
      .player-panel,
      .download-panel,
      .cover-stage {
        min-width: 0;
        max-width: 100%;
      }

      /* =====================================================
         TEXTOS LARGOS
         ===================================================== */

      #preview-title,
      #preview-artist,
      #player-now,
      #player-status,
      #download-modal-title,
      .download-history-info,
      .download-history-info strong,
      .download-history-info span {
        min-width: 0;
        max-width: 100%;
        overflow-wrap: anywhere;
        word-break: break-word;
      }

      #preview-title,
      #preview-artist,
      #player-now {
        text-overflow: ellipsis;
      }

      /* =====================================================
         PLAYER
         ===================================================== */

      .player-panel {
        width: 100%;
        min-width: 0;
        max-width: 100%;
      }

      .cover-stage {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
      }

      #yt-player {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        max-width: 1px !important;
        max-height: 1px !important;
        overflow: hidden !important;
        pointer-events: none !important;
      }

      #seek-bar {
        width: 100%;
        min-width: 0;
        max-width: 100%;
      }

      /* =====================================================
         MODAL DE DESCARGA
         ===================================================== */

      #download-overlay {
        width: 100vw;
        max-width: 100vw;
        overflow: hidden;
        padding:
          max(16px, env(safe-area-inset-top))
          max(16px, env(safe-area-inset-right))
          max(16px, env(safe-area-inset-bottom))
          max(16px, env(safe-area-inset-left));
      }

      #download-overlay > *,
      .download-modal,
      .download-window,
      .download-dialog {
        max-width: 100%;
        min-width: 0;
      }

      #download-progress-bar {
        max-width: 100%;
      }

      /* =====================================================
         TABLET
         ===================================================== */

      @media (max-width: 900px) {
        body {
          width: 100%;
          max-width: 100vw;
        }

        #preview {
          width: 100%;
        }

        .cover-stage {
          width: 100%;
        }
      }

      /* =====================================================
         CELULARES
         ===================================================== */

      @media (max-width: 700px) {
        html,
        body {
          width: 100%;
          min-width: 0;
          max-width: 100%;
          overflow-x: hidden;
        }

        #search-form {
          width: 100%;
          max-width: 100%;
        }

        #preview {
          width: 100%;
          max-width: 100%;
          margin-left: 0;
          margin-right: 0;
        }

        .preview,
        .preview-card,
        .player-panel,
        .download-panel {
          width: 100%;
          max-width: 100%;
        }

        .cover-stage {
          width: 100%;
          max-width: 100%;
          margin-left: auto;
          margin-right: auto;
        }

        #preview-title {
          font-size: clamp(
            16px,
            4.5vw,
            22px
          );
          line-height: 1.2;
        }

        #preview-artist {
          font-size: clamp(
            13px,
            3.7vw,
            17px
          );
        }

        #player-now {
          font-size: clamp(
            13px,
            3.6vw,
            16px
          );
        }

        #download-modal-title {
          font-size: clamp(
            15px,
            4vw,
            20px
          );
          line-height: 1.25;
        }

        #download-overlay {
          align-items: center;
          justify-content: center;
        }

        #download-overlay .download-modal,
        #download-overlay .download-window,
        #download-overlay .download-dialog {
          width: min(
            100%,
            calc(100vw - 24px)
          );
          max-width: calc(100vw - 24px);
          margin-left: auto;
          margin-right: auto;
        }

        .download-history-item {
          width: 100%;
          max-width: 100%;
          min-width: 0;
        }

        .download-history-info {
          flex: 1 1 auto;
          min-width: 0;
        }
      }

      /* =====================================================
         CELULARES MUY PEQUEÑOS
         ===================================================== */

      @media (max-width: 420px) {
        #preview-title {
          font-size: clamp(
            15px,
            5vw,
            19px
          );
        }

        #preview-artist {
          font-size: clamp(
            12px,
            4vw,
            15px
          );
        }

        #search-btn {
          min-width: 0;
        }

        #download-overlay .download-modal,
        #download-overlay .download-window,
        #download-overlay .download-dialog {
          width: calc(100vw - 20px);
          max-width: calc(100vw - 20px);
        }
      }

      /* =====================================================
         PANTALLAS MUY ALTAS / MÓVILES CON SAFE AREA
         ===================================================== */

      @supports (height: 100dvh) {
        #download-overlay {
          min-height: 100dvh;
        }
      }

      /* =====================================================
         EVITAR QUE EL CAMBIO DE CONTENIDO MODIFIQUE
         EL ANCHO DEL DOCUMENTO
         ===================================================== */

      body.app-has-preview {
        overflow-x: hidden;
        scrollbar-gutter: stable;
      }

      body.app-has-preview #preview {
        contain: layout;
      }
    `;

    document.head.appendChild(style);
  }

  function updateResponsiveViewport() {
    const root = document.documentElement;

    const width =
      window.visualViewport
        ? window.visualViewport.width
        : window.innerWidth;

    const height =
      window.visualViewport
        ? window.visualViewport.height
        : window.innerHeight;

    root.style.setProperty(
      '--app-vw',
      `${Math.round(width)}px`
    );

    root.style.setProperty(
      '--app-vh',
      `${Math.round(height)}px`
    );

    root.style.setProperty(
      '--app-width',
      `${Math.round(width)}px`
    );

    root.style.setProperty(
      '--app-height',
      `${Math.round(height)}px`
    );
  }

  function stabilizePreviewLayout() {
    document.body.classList.add(
      'app-has-preview'
    );

    updateResponsiveViewport();

    /*
     * Forzamos al navegador a recalcular el layout
     * después de mostrar la vista previa.
     */
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        updateResponsiveViewport();
      });
    });
  }

  installResponsiveLayout();
  updateResponsiveViewport();

  window.addEventListener(
    'resize',
    updateResponsiveViewport,
    {
      passive: true,
    }
  );

  window.addEventListener(
    'orientationchange',
    () => {
      setTimeout(
        updateResponsiveViewport,
        150
      );

      setTimeout(
        updateResponsiveViewport,
        500
      );
    },
    {
      passive: true,
    }
  );

  if (window.visualViewport) {
    window.visualViewport.addEventListener(
      'resize',
      updateResponsiveViewport,
      {
        passive: true,
      }
    );
  }

  /* =========================================================
     VENTANA DE DESCARGA
     ========================================================= */

  const downloadOverlay =
    document.getElementById(
      'download-overlay'
    );

  const downloadModalTitle =
    document.getElementById(
      'download-modal-title'
    );

  const downloadPercent =
    document.getElementById(
      'download-percent'
    );

  const downloadSize =
    document.getElementById(
      'download-size'
    );

  const downloadProgressBar =
    document.getElementById(
      'download-progress-bar'
    );

  const downloadSpeed =
    document.getElementById(
      'download-speed'
    );

  const downloadEta =
    document.getElementById(
      'download-eta'
    );

  const cancelDownloadBtn =
    document.getElementById(
      'cancel-download-btn'
    );

  let downloadController = null;

  let downloadedSongs = [];

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
    if (
      seconds === null ||
      seconds === undefined
    ) {
      return '—';
    }

    const total =
      Math.round(
        Number(seconds)
      );

    if (
      !Number.isFinite(total) ||
      total < 0
    ) {
      return '—';
    }

    const hours =
      Math.floor(
        total / 3600
      );

    const minutes =
      Math.floor(
        (total % 3600) / 60
      );

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

  function rgbToHex(
    r,
    g,
    b
  ) {
    return `#${[
      r,
      g,
      b,
    ]
      .map((n) =>
        n
          .toString(16)
          .padStart(2, '0')
      )
      .join('')}`.toUpperCase();
  }

  function rgbToHsv(
    r,
    g,
    b
  ) {
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
        h =
          ((g - b) / d) %
          6;
      } else if (
        max === g
      ) {
        h =
          (b - r) / d +
          2;
      } else {
        h =
          (r - g) / d +
          4;
      }

      h /= 6;

      if (h < 0) {
        h += 1;
      }
    }

    const s =
      max === 0
        ? 0
        : d / max;

    return [
      h,
      s,
      max,
    ];
  }

  function hsvToRgb(
    h,
    s,
    v
  ) {
    const i =
      Math.floor(h * 6);

    const f =
      h * 6 - i;

    const p =
      v * (1 - s);

    const q =
      v * (1 - f * s);

    const t =
      v *
      (1 -
        (1 - f) * s);

    const table = [
      [v, t, p],
      [q, v, p],
      [p, v, t],
      [p, q, v],
      [t, p, v],
      [v, p, q],
    ];

    const [
      r,
      g,
      b,
    ] =
      table[i % 6];

    return [
      Math.round(r * 255),
      Math.round(g * 255),
      Math.round(b * 255),
    ];
  }

  function vividize(
    r,
    g,
    b
  ) {
    let [
      h,
      s,
      v,
    ] =
      rgbToHsv(
        r,
        g,
        b
      );

    s = clamp(
      Math.max(s, 0.78) *
        1.4,
      0.82,
      1
    );

    v = clamp(
      Math.max(v, 0.82),
      0.78,
      0.98
    );

    return hsvToRgb(
      h,
      s,
      v
    );
  }

  function paletteFromRgb(
    r,
    g,
    b
  ) {
    const [
      ar,
      ag,
      ab,
    ] =
      vividize(
        r,
        g,
        b
      );

    const [h] =
      rgbToHsv(
        ar,
        ag,
        ab
      );

    const [
      lr,
      lg,
      lb,
    ] =
      hsvToRgb(
        h,
        0.82,
        0.98
      );

    const [
      dr,
      dg,
      db,
    ] =
      hsvToRgb(
        h,
        0.95,
        0.52
      );

    const [
      hr,
      hg,
      hb,
    ] =
      hsvToRgb(
        h,
        0.9,
        1
      );

    const [
      dbr,
      dbg,
      dbb,
    ] =
      hsvToRgb(
        h,
        0.92,
        0.46
      );

    return {
      accent:
        rgbToHex(
          ar,
          ag,
          ab
        ),

      accent_hover:
        rgbToHex(
          hr,
          hg,
          hb
        ),

      accent_deep:
        rgbToHex(
          dbr,
          dbg,
          dbb
        ),

      accent_soft:
        `rgba(${ar}, ${ag}, ${ab}, 0.45)`,

      accent_glow:
        `rgba(${ar}, ${ag}, ${ab}, 0.85)`,

      bg_top:
        `rgba(${lr}, ${lg}, ${lb}, 0.55)`,

      bg_side:
        `rgba(${dr}, ${dg}, ${db}, 0.4)`,

      aurora_1:
        rgbToHex(
          lr,
          lg,
          lb
        ),

      aurora_2:
        rgbToHex(
          ar,
          ag,
          ab
        ),

      aurora_3:
        rgbToHex(
          dr,
          dg,
          db
        ),
    };
  }

  function extractPaletteFromImage(
    img
  ) {
    const canvas =
      document.createElement(
        'canvas'
      );

    canvas.width = 64;
    canvas.height = 64;

    const ctx =
      canvas.getContext(
        '2d',
        {
          willReadFrequently:
            true,
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

    const {
      data,
    } =
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

      const [
        ,
        s,
        v,
      ] =
        rgbToHsv(
          r,
          g,
          b
        );

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
        (0.55 +
          Math.min(
            v,
            0.9
          ));

      const current =
        buckets.get(
          key
        ) || {
          r,
          g,
          b,
          score: 0,
        };

      current.score +=
        weight;

      buckets.set(
        key,
        current
      );
    }

    const ranked = [
      ...buckets.values(),
    ]
      .sort(
        (a, b) =>
          b.score -
          a.score
      )
      .slice(0, 12);

    if (
      !ranked.length
    ) {
      return null;
    }

    let best =
      ranked[0];

    let bestVivid =
      -1;

    for (
      const color of ranked
    ) {
      const [
        ,
        s,
        v,
      ] =
        rgbToHsv(
          color.r,
          color.g,
          color.b
        );

      const vivid =
        color.score *
        (0.35 + s) *
        (0.4 + v);

      if (
        vivid >
        bestVivid
      ) {
        bestVivid =
          vivid;

        best =
          color;
      }
    }

    return paletteFromRgb(
      best.r,
      best.g,
      best.b
    );
  }

  function applyPalette(
    palette
  ) {
    const colors = {
      ...DEFAULT_PALETTE,
      ...(palette || {}),
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

    document.body.classList.add(
      'themed'
    );

    document.body.classList.toggle(
      'cover-black',
      colors.tone ===
        'black'
    );

    document.body.classList.toggle(
      'cover-white',
      colors.tone ===
        'white'
    );
  }

  function resetPalette() {
    applyPalette({
      ...DEFAULT_PALETTE,
      tone: 'color',
    });

    document.body.classList.remove(
      'themed',
      'cover-black',
      'cover-white'
    );
  }

  function coverSrc(
    thumbnail
  ) {
    if (!thumbnail) {
      return '';
    }

    return `/api/cover?src=${encodeURIComponent(
      thumbnail
    )}`;
  }

  function formatBytes(
    bytes
  ) {
    if (
      !Number.isFinite(
        bytes
      ) ||
      bytes <= 0
    ) {
      return '—';
    }

    const units = [
      'B',
      'KB',
      'MB',
      'GB',
    ];

    let value = bytes;
    let unit = 0;

    while (
      value >= 1024 &&
      unit <
        units.length - 1
    ) {
      value /= 1024;
      unit++;
    }

    return `${value.toFixed(
      unit === 0
        ? 0
        : 1
    )} ${units[unit]}`;
  }

  function formatEta(
    seconds
  ) {
    if (
      !Number.isFinite(
        seconds
      ) ||
      seconds < 0
    ) {
      return '—';
    }

    const total =
      Math.round(
        seconds
      );

    const minutes =
      Math.floor(
        total / 60
      );

    const secs =
      total % 60;

    if (
      minutes > 0
    ) {
      return `${minutes}m ${secs}s`;
    }

    return `${secs}s`;
  }

  /* =========================================================
     VENTANA DE DESCARGA
     ========================================================= */

  function openDownloadModal() {
    downloadOverlay.hidden =
      false;

    updateResponsiveViewport();

    downloadModalTitle.textContent =
      `${
        previewTitle.textContent ||
        'Canción'
      }${
        previewArtist.textContent
          ? ` — ${previewArtist.textContent}`
          : ''
      }`;

    downloadPercent.textContent =
      '1%';

    downloadSize.textContent =
      'Preparando descarga…';

    downloadProgressBar.style.width =
      '1%';

    downloadSpeed.textContent =
      '⚡ Calculando…';

    downloadEta.textContent =
      '⏱ Calculando…';
  }

  function closeDownloadModal() {
    downloadOverlay.hidden =
      true;

    document.body.classList.remove(
      'download-open'
    );
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

    if (
      !Number.isFinite(
        safePercent
      )
    ) {
      safePercent = 1;
    }

    if (
      safePercent > 0 &&
      safePercent < 1
    ) {
      safePercent = 1;
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
      `${safePercent.toFixed(
        0
      )}%`;

    downloadProgressBar.style.width =
      `${safePercent}%`;

    if (total > 0) {
      downloadSize.textContent =
        `${formatBytes(
          downloaded
        )} / ${formatBytes(
          total
        )}`;
    } else if (
      downloaded > 0
    ) {
      downloadSize.textContent =
        formatBytes(
          downloaded
        );
    } else {
      downloadSize.textContent =
        'Preparando descarga…';
    }

    downloadSpeed.textContent =
      speed > 0
        ? `⚡ ${formatBytes(
            speed
          )}/s`
        : '⚡ Calculando…';

    downloadEta.textContent =
      eta !== null &&
      eta !== undefined &&
      Number.isFinite(
        eta
      )
        ? `⏱ ${formatEta(
            eta
          )}`
        : '⏱ Calculando…';
  }

  function setSearchLoading(
    loading
  ) {
    searchBtn.disabled =
      loading;

    searchBtn.textContent =
      loading
        ? 'Cargando…'
        : 'Vista previa';
  }

  function showError(
    message
  ) {
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
  }

  formatInputs.forEach(
    (input) =>
      input.addEventListener(
        'change',
        updateFormatUI
      )
  );

  /* =========================================================
     LISTA DE DESCARGAS
     ========================================================= */

  function addDownloadedSong(
    title,
    artist,
    format
  ) {
    downloadedSongs.unshift({
      title:
        title ||
        'Canción',

      artist:
        artist ||
        'Artista desconocido',

      format:
        format.toUpperCase(),

      time:
        new Date(),
    });

    if (
      downloadedSongs.length >
      20
    ) {
      downloadedSongs =
        downloadedSongs.slice(
          0,
          20
        );
    }

    renderDownloadedSongs();
  }

  function findDownloadListContainer() {
    return document.querySelector(
      '#download-history, .download-history, .download-list'
    );
  }

  function renderDownloadedSongs() {
    const container =
      findDownloadListContainer();

    if (!container) {
      return;
    }

    container.innerHTML =
      '';

    if (
      downloadedSongs.length ===
      0
    ) {
      container.innerHTML = `
        <div class="download-empty">
          <span>♪</span>
          <p>Aquí aparecerán tus canciones descargadas.</p>
        </div>
      `;

      return;
    }

    downloadedSongs.forEach(
      (
        song,
        index
      ) => {
        const item =
          document.createElement(
            'div'
          );

        item.className =
          'download-history-item';

        item.innerHTML = `
          <div class="download-history-number">
            ${index + 1}
          </div>

          <div class="download-history-info">
            <strong>${escapeHtml(
              song.title
            )}</strong>
            <span>${escapeHtml(
              song.artist
            )}</span>
          </div>

          <div class="download-history-format">
            ${escapeHtml(
              song.format
            )}
          </div>
        `;

        container.appendChild(
          item
        );
      }
    );
  }

  function escapeHtml(
    value
  ) {
    return String(value)
      .replaceAll(
        '&',
        '&amp;'
      )
      .replaceAll(
        '<',
        '&lt;'
      )
      .replaceAll(
        '>',
        '&gt;'
      )
      .replaceAll(
        '"',
        '&quot;'
      )
      .replaceAll(
        "'",
        '&#039;'
      );
  }

  /* =========================================================
     YOUTUBE
     ========================================================= */

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
      new Promise(
        (resolve) => {
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
        }
      );

    return ytApiPromise;
  }

  function setPlayingUi(
    playing
  ) {
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

  function setPlayerMessage(
    message
  ) {
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
    if (
      progressTimer
    ) {
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
      ytPlayer.getDuration() ||
      0;

    const current =
      ytPlayer.getCurrentTime() ||
      0;

    if (
      duration > 0
    ) {
      seekBar.max =
        String(
          duration
        );

      seekBar.value =
        String(
          current
        );

      timeTotal.textContent =
        formatDuration(
          duration
        );
    }

    timeCurrent.textContent =
      formatDuration(
        current
      );
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

    setPlayingUi(
      false
    );

    if (
      ytPlayer &&
      typeof ytPlayer.destroy ===
        'function'
    ) {
      try {
        ytPlayer.destroy();
      } catch (
        _error
      ) {
        /* ignore */
      }
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
        .prepend(
          fresh
        );
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
            (
              resolve,
              reject
            ) => {
              ytPlayer =
                new window.YT.Player(
                  'yt-player',
                  {
                    height:
                      '1',

                    width:
                      '1',

                    videoId:
                      currentVideoId,

                    playerVars: {
                      autoplay:
                        0,

                      controls:
                        0,

                      disablekb:
                        1,

                      fs: 0,

                      modestbranding:
                        1,

                      playsinline:
                        1,

                      rel: 0,
                    },

                    events: {
                      onReady:
                        (
                          event
                        ) => {
                          ytReady =
                            true;

                          const duration =
                            event.target.getDuration() ||
                            0;

                          seekBar.max =
                            String(
                              duration ||
                                100
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
                        (
                          event
                        ) => {
                          const playing =
                            event.data ===
                            window.YT.PlayerState.PLAYING;

                          setPlayingUi(
                            playing
                          );

                          if (
                            playing
                          ) {
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
                            window.YT.PlayerState.ENDED
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
                            'YouTube bloqueó la reproducción aquí. Prueba abrir el video en YouTube o descarga el audio.'
                          );

                          reject(
                            new Error(
                              'No se pudo reproducir este video.'
                            )
                          );
                        },
                    },
                  }
                );
            }
          )
      );
  }

  async function togglePlayback() {
    if (
      !currentVideoId
    ) {
      return;
    }

    playBtn.disabled =
      true;

    setPlayerMessage(
      ''
    );

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
    } catch (
      error
    ) {
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
      seeking =
        true;

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
      seeking =
        false;

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

  function detectCoverTone(
    img
  ) {
    const probe =
      document.createElement(
        'canvas'
      );

    probe.width =
      32;

    probe.height =
      32;

    const ctx =
      probe.getContext(
        '2d',
        {
          willReadFrequently:
            true,
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

    const {
      data,
    } =
      ctx.getImageData(
        0,
        0,
        32,
        32
      );

    let sat =
      0;

    let val =
      0;

    const count =
      data.length / 4;

    for (
      let i = 0;
      i < data.length;
      i += 4
    ) {
      const [
        ,
        s,
        v,
      ] =
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

    if (
      sat < 0.16
    ) {
      if (
        val < 0.34
      ) {
        return 'black';
      }

      if (
        val > 0.72
      ) {
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

      if (
        tone === 'black'
      ) {
        applyPalette(
          MONO_BLACK
        );

        return;
      }

      if (
        tone === 'white'
      ) {
        applyPalette(
          MONO_WHITE
        );

        return;
      }

      const extracted =
        extractPaletteFromImage(
          previewThumb
        );

      if (
        extracted
      ) {
        applyPalette(
          extracted
        );
      }
    }
  );

  /* =========================================================
     BÚSQUEDA
     ========================================================= */

  form.addEventListener(
    'submit',
    async (
      event
    ) => {
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

      document.body.classList.remove(
        'app-has-preview'
      );

      downloadStatus.hidden =
        true;

      destroyPlayer();

      setPlayerMessage(
        ''
      );

      try {
        const response =
          await fetch(
            `/api/info?url=${encodeURIComponent(
              url
            )}`
          );

        const data =
          await response.json();

        if (
          !response.ok
        ) {
          throw new Error(
            data.detail ||
              'No pudimos leer ese enlace.'
          );
        }

        currentUrl =
          url;

        currentVideoId =
          data.id || '';

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
          data.title ||
          'Sin título';

        previewArtist.textContent =
          data.uploader ||
          'Artista desconocido';

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

        /*
         * Mostramos la vista previa y estabilizamos
         * inmediatamente el layout.
         */
        preview.hidden =
          false;

        stabilizePreviewLayout();

        updateFormatUI();

        /*
         * Segundo recalculo después de que el navegador
         * haya pintado la portada/contenido.
         */
        requestAnimationFrame(
          () => {
            updateResponsiveViewport();
          }
        );
      } catch (
        error
      ) {
        resetPalette();

        document.body.classList.remove(
          'app-has-preview'
        );

        showError(
          error.message ||
            'No pudimos leer ese enlace. Verifica que sea un enlace válido de YouTube o YouTube Music.'
        );
      } finally {
        setSearchLoading(
          false
        );
      }
    }
  );

  /* =========================================================
     DESCARGA
     ========================================================= */

  downloadBtn.addEventListener(
    'click',
    async () => {
      if (!currentUrl) {
        return;
      }

      const format =
        selectedFormat();

      const title =
        previewTitle.textContent ||
        'audio';

      const artist =
        previewArtist.textContent ||
        'Artista desconocido';

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
              method:
                'POST',

              headers: {
                'Content-Type':
                  'application/json',
              },

              body:
                JSON.stringify(
                  {
                    url:
                      currentUrl,

                    format,
                  }
                ),

              signal:
                downloadController.signal,
            }
          );

        if (
          !response.ok
        ) {
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

        const match =
          disposition.match(
            /filename\*?=(?:UTF-8''|")?([^";]+)"?/i
          );

        let filename =
          match
            ? decodeURIComponent(
                match[1]
              )
            : '';

        if (!filename) {
          filename =
            `${sanitizeFilename(
              title
            )} - ${sanitizeFilename(
              artist
            )}.${format}`;
        }

        if (
          !response.body
        ) {
          throw new Error(
            'El navegador no permite mostrar el progreso.'
          );
        }

        const reader =
          response.body.getReader();

        const chunks =
          [];

        let received =
          0;

        const startTime =
          performance.now();

        updateDownloadProgress(
          total > 0
            ? 1
            : 2,
          0,
          total,
          0,
          null
        );

        while (
          true
        ) {
          const {
            done,
            value,
          } =
            await reader.read();

          if (
            done
          ) {
            break;
          }

          chunks.push(
            value
          );

          received +=
            value.length;

          const elapsed =
            (performance.now() -
              startTime) /
            1000;

          const speed =
            elapsed > 0
              ? received /
                elapsed
              : 0;

          const percent =
            total > 0
              ? (received /
                  total) *
                100
              : Math.min(
                  95,
                  Math.max(
                    5,
                    received /
                      1024 /
                      1024
                  )
                );

          const remaining =
            total > 0 &&
            speed > 0
              ? (total -
                  received) /
                speed
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

        addDownloadedSong(
          title,
          artist,
          format
        );

        downloadStatus.textContent =
          '✓ Descarga completada correctamente.';

        downloadStatus.hidden =
          false;

        setTimeout(
          () => {
            closeDownloadModal();
          },
          700
        );
      } catch (
        error
      ) {
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
      if (
        downloadController
      ) {
        downloadController.abort();
      }
    }
  );

  function sanitizeFilename(
    name
  ) {
    return String(
      name || 'audio'
    )
      .replace(
        /[<>:"/\\|?*\x00-\x1F]/g,
        ''
      )
      .replace(
        /\s+/g,
        ' '
      )
      .trim()
      .replace(
        /\.+$/,
        ''
      )
      .slice(
        0,
        150
      );
  }

  renderDownloadedSongs();

  /* =========================================================
     MOVIMIENTO DE LA VENTANA DE DESCARGA
     ========================================================= */

  if (
    downloadOverlay
  ) {
    let mouseX = 0;
    let mouseY = 0;

    let targetX = 0;
    let targetY = 0;

    let currentX = 0;
    let currentY = 0;

    document.addEventListener(
      'mousemove',
      (event) => {
        /*
         * En móviles no necesitamos seguir el cursor.
         */
        if (
          window.innerWidth <=
          700
        ) {
          targetX = 0;
          targetY = 0;
          return;
        }

        mouseX =
          event.clientX /
          window.innerWidth;

        mouseY =
          event.clientY /
          window.innerHeight;

        targetX =
          (mouseX - 0.5) *
          24;

        targetY =
          (mouseY - 0.5) *
          16;
      }
    );

    function animateDownloadWindow() {
      currentX +=
        (targetX -
          currentX) *
        0.08;

      currentY +=
        (targetY -
          currentY) *
        0.08;

      downloadOverlay.style.setProperty(
        '--download-move-x',
        `${currentX.toFixed(
          2
        )}px`
      );

      downloadOverlay.style.setProperty(
        '--download-move-y',
        `${currentY.toFixed(
          2
        )}px`
      );

      requestAnimationFrame(
        animateDownloadWindow
      );
    }

    animateDownloadWindow();
  }
})();
```
