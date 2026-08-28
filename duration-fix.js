(() => {
  const previewDuration = document.getElementById('preview-duration');
  const timeTotal = document.getElementById('time-total');
  if (!previewDuration || !timeTotal) return;

  const copyDuration = () => {
    const value = (timeTotal.textContent || '').trim();
    if (!value || value === '0:00' || value === '—') return;
    if (/^\d+:\d{2}(?::\d{2})?$/.test(value)) {
      previewDuration.textContent = value;
    }
  };

  // The embedded YouTube IFrame player has the real duration even when the
  // server-side extractor is blocked. app.js already updates #time-total from
  // player.getDuration(); we mirror that value into the information card.
  const observer = new MutationObserver(copyDuration);
  observer.observe(timeTotal, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  setInterval(copyDuration, 500);
  copyDuration();
})();
