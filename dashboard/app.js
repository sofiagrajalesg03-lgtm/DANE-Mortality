/* Dashboard de mortalidad. Sin servidor: carga data/datos.json (paso 3) y, si existe,
   data/medellin_densidad.geojson (paso 4); filtra y suma en el navegador. */
(() => {
  'use strict';

  // ---------- utilidades ----------
  const $ = (s, r = document) => r.querySelector(s);
  const nf = new Intl.NumberFormat('es-CO');
  const nf1 = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  // Abreviatura del eje: el formato compacto del navegador mezcla "k" y "K" en es-CO.
  const nfm = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 });
  const nfc = { format: v => (Math.abs(v) >= 1000 ? nfm.format(v / 1000) + ' mil' : nfm.format(v)) };
  const fmt = n => nf.format(Math.round(n));
  const pct = (a, b) => (b ? nf1.format((a / b) * 100) + ' %' : '—');
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const alpha = (hex, a) => {
    let h = hex.replace('#', '');
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    const v = parseInt(h, 16);
    return `rgba(${(v >> 16) & 255},${(v >> 8) & 255},${v & 255},${a})`;
  };
  const SEXVAR = ['--s1', '--s2', '--s3'];

  // Posición de cada campo en las filas de los cubos (ver scripts/03_build_dashboard_data.py)
  const NAC = { a: 0, d: 1, c: 2, e: 3, s: 4, n: 5 };
  const MED = { a: 0, c: 1, e: 2, s: 3, n: 4 };

  let D = null;          // datos.json
  let GEO = null;        // medellin_densidad.geojson (opcional)
  const S = { anio: 0, sexo: '', dpto: '', tab: 'col' };
  const charts = {};
  let map = null, geoLayer = null;

  const sexF = () => (S.sexo === '' ? null : +S.sexo);
  const dptF = () => (S.dpto === '' ? null : +S.dpto);

  // ---------- agregaciones sobre los cubos ----------
  function ok(r, C, f) {
    return (f.a == null || r[C.a] === f.a) && (f.s == null || r[C.s] === f.s) &&
           (f.d == null || C.d === undefined || r[C.d] === f.d);
  }
  function total(rows, C, f) {
    let t = 0;
    for (const r of rows) if (ok(r, C, f)) t += r[C.n];
    return t;
  }
  function agg(rows, C, key, f) {
    const m = new Map(), k = C[key];
    for (const r of rows) if (ok(r, C, f)) m.set(r[k], (m.get(r[k]) || 0) + r[C.n]);
    return m;
  }

  // ---------- carga ----------
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
    return r.json();
  }

  // La capa de Medellín (puede pesar cientos de KB) y Leaflet solo se descargan al abrir esa pestaña.
  let geoPromise = null;
  function loadGeo() {
    if (!geoPromise) {
      geoPromise = getJSON('data/medellin_densidad.geojson').then(g => { GEO = g; }).catch(() => { GEO = null; });
    }
    return geoPromise;
  }

  let leafletPromise = null;
  function loadLeaflet() {
    if (!leafletPromise) {
      const css = new Promise((ok, err) => {
        const l = document.createElement('link');
        l.rel = 'stylesheet'; l.href = 'vendor/leaflet.css'; l.onload = ok; l.onerror = err;
        // Antes de styles.css, para que las reglas de ese archivo sigan ganando sobre las de Leaflet.
        document.head.insertBefore(l, document.querySelector('link[href="styles.css"]'));
      });
      const js = new Promise((ok, err) => {
        const s = document.createElement('script');
        s.src = 'vendor/leaflet.js'; s.onload = ok; s.onerror = err;
        document.head.appendChild(s);
      });
      leafletPromise = Promise.all([css, js]).catch(e => { leafletPromise = null; throw e; });
    }
    return leafletPromise;
  }

  async function init() {
    if (typeof Chart === 'undefined') return fail('No se cargó Chart.js (carpeta vendor/).');
    try {
      D = await getJSON('data/datos.json');
    } catch (e) {
      return fail('No pude cargar data/datos.json. Si abriste index.html con doble clic, el navegador ' +
        'bloquea la carga: corre "python -m http.server 8000" dentro de dashboard/ y abre ' +
        'http://localhost:8000. Si el archivo no existe, corre python scripts/03_build_dashboard_data.py. (' + e.message + ')');
    }
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 12;
    buildControls();
    bind();
    render();
    document.body.classList.remove('loading');
  }

  function fail(msg) {
    const el = $('#error');
    el.textContent = msg;
    el.hidden = false;
    document.body.classList.remove('loading');
  }

  // ---------- controles ----------
  function buildControls() {
    const A = D.dims.anios;
    $('#f-anio').innerHTML = A.map((a, i) => `<option value="${i}">${esc(a.label)}</option>`).join('');
    // Por defecto: el año completo más reciente (un año parcial no debe ser el primer vistazo).
    let def = A.length - 1;
    for (let i = A.length - 1; i >= 0; i--) if (!A[i].parcial) { def = i; break; }
    S.anio = def;
    $('#f-anio').value = String(def);
    $('#f-dpto').insertAdjacentHTML('beforeend',
      D.dims.dptos.map((n, i) => `<option value="${i}">${esc(n)}</option>`).join(''));
  }

  function bind() {
    $('#f-anio').addEventListener('change', e => { S.anio = +e.target.value; render(); });
    $('#f-sexo').addEventListener('change', e => { S.sexo = e.target.value; render(); });
    $('#f-dpto').addEventListener('change', e => { S.dpto = e.target.value; render(); });
    const tabs = [$('#tab-col'), $('#tab-med')];
    tabs.forEach((b, i) => {
      b.addEventListener('click', () => setTab(i ? 'med' : 'col'));
      b.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { setTab(i ? 'col' : 'med'); tabs[i ? 0 : 1].focus(); }
      });
    });
    document.querySelectorAll('.card').forEach(card => {
      const btn = $('.toggle', card);
      if (!btn) return;
      btn.addEventListener('click', () => {
        const t = $('.view-table', card), c = $('.view-chart', card);
        const showTable = t.hidden;
        t.hidden = !showTable;
        c.hidden = showTable;
        btn.textContent = showTable ? 'Ver gráfico' : 'Ver tabla';
      });
    });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => render());
  }

  function setTab(t) {
    S.tab = t;
    $('#panel-col').hidden = t !== 'col';
    $('#panel-med').hidden = t !== 'med';
    [['#tab-col', 'col'], ['#tab-med', 'med']].forEach(([sel, k]) => {
      const b = $(sel);
      b.setAttribute('aria-selected', String(k === t));
      b.tabIndex = k === t ? 0 : -1;
    });
    const sel = $('#f-dpto');
    sel.disabled = t === 'med';
    sel.title = t === 'med' ? 'No aplica: esta vista es solo de Medellín' : '';
    // La primera vez que se abre Medellín se espera a la capa de población antes de dibujar.
    if (t === 'med' && !geoPromise) loadGeo().then(() => { if (S.tab === 'med') render(); });
    else render();
  }

  // ---------- render general ----------
  function render() {
    const an = D.dims.anios[S.anio];
    const sexo = S.sexo === '' ? 'Hombres y mujeres' : (S.sexo === '0' ? 'Hombres' : 'Mujeres');
    const lugar = S.tab === 'med' ? 'Residentes de Medellín'
      : (S.dpto === '' ? 'Todo el país' : D.dims.dptos[+S.dpto]);
    $('#ctx').textContent = `Mostrando: ${an.label} · ${sexo} · ${lugar}`;

    const aviso = $('#aviso');
    if (an.parcial) {
      const m = an.periodo.match(/(ocurridas y reportadas entre .*?)\)?\s*$/i);
      aviso.textContent = `${an.label} es un periodo parcial y preliminar (${m ? m[1] : an.periodo}). ` +
        'No es comparable con un año completo, por eso no se calcula variación anual ni tasa.';
      aviso.hidden = false;
    } else if (an.preliminar) {
      aviso.textContent = `${an.label}: cifras preliminares, pueden cambiar cuando el DANE publique las definitivas.`;
      aviso.hidden = false;
    } else {
      aviso.hidden = true;
    }

    if (S.tab === 'col') renderCol(); else renderMed();
    renderFoot(an);
  }

  function renderFoot(an) {
    const q = D.meta.calidad[String(an.anio)];
    const partes = [
      `<p>Fuente: ${esc(D.meta.fuente)}. Datos procesados el ${esc(D.meta.generado)}.` +
      (S.tab === 'med' ? ' Población de Medellín: Alcaldía de Medellín (proyección DANE, base Censo 2018).' : '') + '</p>',
      '<p>Las defunciones se asignan por <strong>lugar de residencia</strong> del fallecido, no por el lugar donde ocurrió la muerte.</p>',
    ];
    if (q && S.tab === 'col') {
      partes.push(`<p>Del total nacional de ${esc(an.label)}, ${fmt(q.extranjero)} (${pct(q.extranjero, q.total)}) residían en el exterior y ` +
        `${fmt(q.sin_info)} (${pct(q.sin_info, q.total)}) no tienen información de residencia: no se asignan a ningún departamento.</p>`);
    }
    $('#foot').innerHTML = partes.join('');
  }

  // ---------- gráficos ----------
  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--surface'), titleColor: css('--text'), bodyColor: css('--text-2'),
          footerColor: css('--text-2'), borderColor: css('--border-strong'), borderWidth: 1,
          padding: 10, boxPadding: 4, cornerRadius: 6,
        },
      },
      scales: {
        x: { grid: { display: false }, border: { color: css('--axis') },
             ticks: { color: css('--text-2'), maxRotation: 0, autoSkip: false } },
        y: { beginAtZero: true, grid: { color: css('--grid') }, border: { display: false },
             ticks: { color: css('--text-2'), callback: v => nfc.format(v) } },
      },
    };
  }

  function legend(show) {
    return { display: show, position: 'top', align: 'start',
      labels: { color: css('--text-2'), usePointStyle: true, pointStyle: 'rectRounded', boxWidth: 8, boxHeight: 8 } };
  }

  function makeChart(id, cfg) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($('#' + id), cfg);
  }

  const shortEdad = l => l.replace(' años', '').replace('Menor 1', '<1').replace('100 y más', '100+').replace('Edad desconocida', 'Desc.');

  // Defunciones por año (columnas apiladas por sexo). Devuelve filas para la vista de tabla.
  function yearChart(id, rows, C, f) {
    const A = D.dims.anios;
    const sexes = (f.s == null ? [0, 1, 2] : [f.s])
      .filter(s => A.some((_, i) => total(rows, C, { ...f, a: i, s }) > 0));
    const sets = sexes.map(s => {
      const col = css(SEXVAR[s]);
      return {
        label: D.dims.sexos[s],
        data: A.map((_, i) => total(rows, C, { ...f, a: i, s })),
        backgroundColor: c => (A[c.dataIndex].parcial ? alpha(col, 0.55) : col),
        borderColor: css('--surface'), borderWidth: 1, borderRadius: 3, maxBarThickness: 56,
      };
    });
    const labels = A.map(a => (a.parcial ? [String(a.anio), a.label.replace(/^\d+ /, '')] : String(a.anio)));
    const o = baseOptions();
    o.scales.x.stacked = o.scales.y.stacked = true;
    o.plugins.legend = legend(sets.length > 1);
    o.plugins.tooltip.callbacks = {
      title: it => A[it[0].dataIndex].label,
      label: it => ` ${it.dataset.label}: ${fmt(it.parsed.y)}`,
      footer: it => (it.length > 1 ? 'Total: ' + fmt(it.reduce((t, x) => t + x.parsed.y, 0)) : ''),
    };
    makeChart(id, { type: 'bar', data: { labels, datasets: sets }, options: o });
    return {
      headers: ['Periodo', ...sexes.map(s => D.dims.sexos[s]), 'Total'],
      rows: A.map((a, i) => [a.label, ...sets.map(s => s.data[i]), sets.reduce((t, s) => t + s.data[i], 0)]),
    };
  }

  // Defunciones por grupo de edad (columnas agrupadas hombre/mujer).
  function edadChart(id, subId, rows, C, f) {
    const E = D.dims.edades;
    const sexes = f.s == null ? [0, 1] : [f.s];
    const sets = sexes.map(s => {
      const m = agg(rows, C, 'e', { ...f, s });
      return {
        label: D.dims.sexos[s], data: E.map((_, i) => m.get(i) || 0), backgroundColor: css(SEXVAR[s]),
        borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: 'bottom', maxBarThickness: 24,
      };
    });
    const o = baseOptions();
    o.plugins.legend = legend(sets.length > 1);
    o.plugins.tooltip.callbacks = {
      title: it => E[it[0].dataIndex],
      label: it => ` ${it.dataset.label}: ${fmt(it.parsed.y)}`,
    };
    o.scales.x.title = { display: true, text: 'Grupo de edad (años)', color: css('--text-2') };
    o.scales.x.ticks.maxRotation = 90; // en pantallas estrechas las 10 etiquetas se giran en vez de montarse
    makeChart(id, { type: 'bar', data: { labels: E.map(shortEdad), datasets: sets }, options: o });

    const ind = f.s == null ? total(rows, C, { ...f, s: 2 }) : 0;
    $('#' + subId).textContent = (f.a != null ? D.dims.anios[f.a].label : '') +
      (ind > 0 ? ` · excluye ${fmt(ind)} de sexo indeterminado` : '');
    const all = agg(rows, C, 'e', f);
    return {
      headers: ['Grupo de edad', ...sexes.map(s => D.dims.sexos[s]), 'Total'],
      rows: E.map((e, i) => [e, ...sets.map(s => s.data[i]), all.get(i) || 0]),
    };
  }

  // ---------- rankings (barras HTML) ----------
  function renderRank(sel, items, { unit = '', selIdx = -1 } = {}) {
    const max = Math.max(1, ...items.map(i => i.value));
    $(sel).innerHTML = items.map((it, k) => `
      <li class="${k === selIdx ? 'sel' : ''}" title="${esc(it.title || it.label)}">
        <span class="lab">${esc(it.label)}</span>
        <span class="trk"><i style="width:${(it.value / max) * 100}%"></i></span>
        <span class="val">${it.text != null ? esc(it.text) : fmt(it.value)}${unit ? `<small>${unit}</small>` : ''}${it.extra ? `<small>${esc(it.extra)}</small>` : ''}</span>
      </li>`).join('');
  }

  function renderTable(cardSel, headers, rows) {
    const cell = v => (typeof v === 'number' ? fmt(v) : esc(v));
    $('.view-table', $(cardSel)).innerHTML =
      `<table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>` +
      rows.map(r => `<tr>${r.map(v => `<td>${cell(v)}</td>`).join('')}</tr>`).join('') + '</tbody></table>';
  }

  function causaRank(rows, C, f, sel, cardSel) {
    const m = agg(rows, C, 'c', f);
    const all = [...m.entries()].sort((a, b) => b[1] - a[1]);
    const tot = all.reduce((t, x) => t + x[1], 0);
    const items = all.slice(0, 10).map(([c, n]) => ({
      label: D.dims.causas[c].nombre, value: n, title: `${D.dims.causas[c].cod} · ${D.dims.causas[c].nombre}`,
      extra: pct(n, tot),
    }));
    renderRank(sel, items);
    renderTable(cardSel, ['Código', 'Causa', 'Defunciones', '%'],
      all.map(([c, n]) => [D.dims.causas[c].cod, D.dims.causas[c].nombre, n, pct(n, tot)]));
    return { all, tot };
  }

  // ---------- vista Colombia ----------
  function renderCol() {
    const A = D.dims.anios, an = A[S.anio];
    const f = { a: S.anio, s: sexF(), d: dptF() };
    const tot = total(D.nac, NAC, f);

    $('#k-total').textContent = fmt(tot);
    $('#k-total-s').textContent = f.d == null
      ? (an.parcial ? 'periodo parcial' : 'por lugar de residencia')
      : `${pct(tot, total(D.nac, NAC, { ...f, d: null }))} del total nacional`;

    // Variación: solo entre años completos y consecutivos.
    const prev = S.anio > 0 ? A[S.anio - 1] : null;
    if (!prev || prev.anio !== an.anio - 1) {
      setKpi('k-var', '—', 'no hay año anterior', 'Variación anual');
    } else if (an.parcial || prev.parcial) {
      setKpi('k-var', '—', 'periodos no comparables (año parcial)', `Variación vs. ${prev.label}`);
    } else {
      const pt = total(D.nac, NAC, { ...f, a: S.anio - 1 });
      const d = pt ? ((tot - pt) / pt) * 100 : null;
      setKpi('k-var', d == null ? '—' : (d >= 0 ? '+' : '−') + nf1.format(Math.abs(d)) + ' %',
        `${fmt(tot)} frente a ${fmt(pt)}`, `Variación vs. ${prev.label}`);
    }

    const { all } = causaRank(D.nac, NAC, f, '#r-causas', '#card-causas');
    if (all.length) {
      $('#k-causa').textContent = D.dims.causas[all[0][0]].nombre;
      $('#k-causa-s').textContent = `${fmt(all[0][1])} defunciones · ${pct(all[0][1], tot)}`;
    } else {
      $('#k-causa').textContent = '—'; $('#k-causa-s').textContent = '';
    }

    const old = new Set(D.dims.edades.map((l, i) => (/^(65|85|100)/.test(l) ? i : -1)).filter(i => i >= 0));
    let nOld = 0;
    for (const r of D.nac) if (ok(r, NAC, f) && old.has(r[NAC.e])) nOld += r[NAC.n];
    $('#k-65').textContent = pct(nOld, tot);
    $('#k-65-s').textContent = `${fmt(nOld)} defunciones`;

    const ty = yearChart('c-anual', D.nac, NAC, { s: f.s, d: f.d });
    $('#sub-anual').textContent = 'Por sexo' + (an.parcial || A.some(a => a.parcial) ? ' · el periodo parcial se muestra más claro' : '');
    renderTable('#card-anual', ty.headers, ty.rows);

    const te = edadChart('c-edad', 'sub-edad', D.nac, NAC, f);
    renderTable('#card-edad', te.headers, te.rows);

    // Departamentos: ignora el filtro de departamento (es un ranking), respeta año y sexo.
    const iExt = D.dims.dptos.indexOf('Extranjero'), iSin = D.dims.dptos.indexOf('Sin información');
    const m = agg(D.nac, NAC, 'd', { a: S.anio, s: f.s });
    const deptos = [...m.entries()].filter(([d]) => d !== iExt && d !== iSin).sort((a, b) => b[1] - a[1]);
    const totDeptos = deptos.reduce((t, x) => t + x[1], 0);
    const top = deptos.slice(0, 10);
    renderRank('#r-dptos', top.map(([d, n]) => ({ label: D.dims.dptos[d], value: n, extra: pct(n, totDeptos) })),
      { selIdx: top.findIndex(([d]) => d === f.d) });
    const noAsig = (m.get(iExt) || 0) + (m.get(iSin) || 0);
    $('#foot-dptos').textContent = `Porcentaje sobre los ${fmt(totDeptos)} asignados a un departamento. ` +
      `No incluye ${fmt(noAsig)} residentes en el exterior o sin información.`;
    renderTable('#card-dptos', ['Departamento', 'Defunciones', '%'],
      [...deptos.map(([d, n]) => [D.dims.dptos[d], n, pct(n, totDeptos)]),
       ['Extranjero', m.get(iExt) || 0, '—'], ['Sin información', m.get(iSin) || 0, '—']]);
  }

  function setKpi(id, v, s, label) {
    $('#' + id).textContent = v;
    $('#' + id + '-s').textContent = s;
    if (label) $('#' + id + '-l').textContent = label;
  }

  // ---------- vista Medellín ----------
  const popOf = anio => {
    if (!GEO) return null;
    let t = 0;
    for (const ft of GEO.features) {
      const v = ft.properties['pob_' + anio];
      if (v == null) return null;
      t += v;
    }
    return t;
  };
  const areaTotal = () => GEO.features.reduce((t, ft) => t + ft.properties.area_km2, 0);

  function renderMed() {
    const A = D.dims.anios, an = A[S.anio];
    const f = { a: S.anio, s: sexF() };
    const tot = total(D.med, MED, f);
    $('#m-total').textContent = fmt(tot);
    $('#m-total-s').textContent = an.parcial ? 'periodo parcial' : 'por lugar de residencia';

    const pop = popOf(an.anio);
    if (pop == null) {
      $('#m-pob').textContent = 'n/d';
      $('#m-pob-s').textContent = GEO ? `sin proyección para ${an.anio}` : 'falta correr el paso 4 (densidad)';
      $('#m-dens').textContent = 'n/d'; $('#m-dens-s').textContent = '';
    } else {
      $('#m-pob').textContent = fmt(pop);
      $('#m-pob-s').textContent = `proyección al 30 de junio de ${an.anio}`;
      $('#m-dens').textContent = fmt(pop / areaTotal());
      $('#m-dens-s').textContent = 'hab/km² (incluye zona rural)';
    }
    if (pop == null) {
      $('#m-tasa').textContent = 'n/d'; $('#m-tasa-s').textContent = 'requiere la población proyectada';
    } else if (an.parcial) {
      $('#m-tasa').textContent = 'n/d'; $('#m-tasa-s').textContent = 'periodo parcial: no es una tasa anual';
    } else if (f.s != null) {
      $('#m-tasa').textContent = 'n/d'; $('#m-tasa-s').textContent = 'la población proyectada no viene por sexo';
    } else {
      $('#m-tasa').textContent = nf1.format((tot / pop) * 1e5);
      $('#m-tasa-s').textContent = 'defunciones ÷ población proyectada';
    }

    const ty = yearChart('c-m-anual', D.med, MED, { s: f.s });
    renderTable('#card-m-anual', ty.headers, ty.rows);
    causaRank(D.med, MED, f, '#r-m-causas', '#card-m-causas');
    const te = edadChart('c-m-edad', 'sub-m-edad', D.med, MED, f);
    renderTable('#card-m-edad', te.headers, te.rows);

    renderMapa(an);
  }

  // ---------- mapa de densidad ----------
  const dens = (ft, anio) => {
    const p = ft.properties;
    return p['pob_' + anio] != null && p.area_km2 ? p['pob_' + anio] / p.area_km2 : null;
  };
  const seqColors = () => [1, 2, 3, 4, 5].map(i => css('--seq-' + i));

  function breaks(vals) {
    const v = [...vals].sort((a, b) => a - b);
    return [1, 2, 3, 4].map(i => v[Math.min(v.length - 1, Math.floor((i * v.length) / 5))]);
  }
  const classOf = (x, th) => th.filter(t => x >= t).length;

  function renderMapa(an) {
    const vacio = !GEO || !GEO.features.length;
    $('#mapa-vacio').hidden = !vacio;
    $('#mapa-grid').hidden = vacio;
    if (vacio) return;

    if (typeof L === 'undefined') {  // Leaflet aún no se ha descargado: se pide y se vuelve a dibujar
      loadLeaflet().then(() => { if (S.tab === 'med') renderMapa(D.dims.anios[S.anio]); }).catch(() => {
        $('#mapa-grid').hidden = true;
        const v = $('#mapa-vacio');
        v.textContent = 'No se pudo cargar el mapa (vendor/leaflet.js).';
        v.hidden = false;
      });
      return;
    }

    const vals = GEO.features.map(ft => dens(ft, an.anio)).filter(v => v != null);
    if (!vals.length) { $('#mapa-vacio').hidden = false; $('#mapa-grid').hidden = true; return; }
    const th = breaks(vals), cols = seqColors();
    const colorOf = ft => { const d = dens(ft, an.anio); return d == null ? css('--surface-2') : cols[classOf(d, th)]; };

    if (!map) {
      map = L.map('map', { zoomSnap: 0.25, scrollWheelZoom: false });
      map.attributionControl.setPrefix(false);
      map.attributionControl.addAttribution('Datos: Alcaldía de Medellín · DANE');
      geoLayer = L.geoJSON(GEO, {
        style: () => ({ weight: 1.5, color: css('--surface'), fillOpacity: 1 }),
        onEachFeature: (ft, layer) => layer.bindTooltip(() => {
          const p = ft.properties, y = D.dims.anios[S.anio].anio, d = dens(ft, y);
          return `<strong>${esc(p.nombre)}</strong><br>${esc(p.tipo)}<br>` +
            `${d == null ? 'n/d' : fmt(d) + ' hab/km²'}<br>${p['pob_' + y] == null ? 'n/d' : fmt(p['pob_' + y]) + ' hab.'} · ${nf1.format(p.area_km2)} km²`;
        }, { sticky: true }),
      }).addTo(map);
    }
    map.invalidateSize();
    map.fitBounds(geoLayer.getBounds(), { padding: [8, 8] });
    geoLayer.eachLayer(l => l.setStyle({ fillColor: colorOf(l.feature), color: css('--surface') }));

    const lo = Math.min(...vals), hi = Math.max(...vals);
    const edges = [lo, ...th, hi];
    $('#map-legend').innerHTML = cols.map((c, i) =>
      `<span><i style="background:${c}"></i>${fmt(edges[i])}–${fmt(edges[i + 1])}</span>`).join('') +
      '<span>hab/km²</span>';

    const items = GEO.features
      .map(ft => ({ ft, d: dens(ft, an.anio) })).filter(x => x.d != null).sort((a, b) => b.d - a.d)
      .map(({ ft, d }) => ({ label: `${ft.properties.nombre} (${ft.properties.tipo.toLowerCase()})`, value: d, text: fmt(d) }));
    renderRank('#r-dens', items, { unit: 'hab/km²' });
  }

  init();
})();
