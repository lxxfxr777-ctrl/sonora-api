(() => {
  const form = document.getElementById('search-form');
  const input = document.getElementById('url-input');
  const button = document.getElementById('search-btn');
  const error = document.getElementById('search-error');
  if (!form || !input || !button) return;

  const results = document.createElement('div');
  results.id = 'search-results';
  results.style.cssText = 'display:grid;gap:10px;margin-top:16px;max-height:420px;overflow:auto;';
  form.parentElement.appendChild(results);

  const style = document.createElement('style');
  style.textContent = `
    #search-results .sonora-result{display:grid;grid-template-columns:64px 1fr auto;gap:12px;align-items:center;padding:10px;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(0,0,0,.22);cursor:pointer;text-align:left;color:inherit;width:100%;}
    #search-results .sonora-result:hover{background:rgba(0,0,0,.34);transform:translateY(-1px)}
    #search-results img{width:64px;height:64px;border-radius:10px;object-fit:cover}
    #search-results strong{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:15px}
    #search-results span{display:block;margin-top:5px;opacity:.7;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #search-results small{opacity:.55}
    @media(max-width:600px){#search-results .sonora-result{grid-template-columns:52px 1fr}#search-results img{width:52px;height:52px}#search-results small{display:none}}
  `;
  document.head.appendChild(style);

  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
  }

  function duration(iso) {
    if (!iso) return '';
    const m = iso.match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/);
    if (!m) return '';
    const h = Number(m[1] || 0), min = Number(m[2] || 0), sec = Number(m[3] || 0);
    return h ? `${h}:${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}` : `${min}:${String(sec).padStart(2,'0')}`;
  }

  function clearResults() { results.innerHTML = ''; results.hidden = true; }

  function showResults(items) {
    results.innerHTML = '';
    results.hidden = false;
    if (!items.length) {
      results.innerHTML = '<div class="status">No encontramos canciones con esa búsqueda.</div>';
      return;
    }
    items.forEach(item => {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'sonora-result';
      el.innerHTML = `
        <img src="${esc(item.thumbnail || '')}" alt="">
        <div><strong>${esc(item.title)}</strong><span>${esc(item.uploader || 'Artista desconocido')}</span></div>
        <small>${esc(duration(item.duration_iso))}</small>
      `;
      el.addEventListener('click', () => {
        input.value = item.webpage_url;
        window.__sonoraSelectingResult = true;
        clearResults();
        form.requestSubmit();
        window.__sonoraSelectingResult = false;
      });
      results.appendChild(el);
    });
  }

  form.addEventListener('submit', async event => {
    if (window.__sonoraSelectingResult) return;

    event.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    clearResults();
    error.hidden = true;
    button.disabled = true;
    button.textContent = 'Buscando…';

    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=8`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'No se pudo realizar la búsqueda.');
      showResults(data.results || []);
    } catch (err) {
      error.textContent = err.message || 'No se pudo realizar la búsqueda.';
      error.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = 'Buscar';
    }
  }, true);
})();
