/* Plotly owns only presentation. All technical values come from the API. */
const grafTilstander = new Map();
const kopi = value => JSON.parse(JSON.stringify(value));

function rensGrafer(omraade) {
  omraade.querySelectorAll('.interaktiv-graf').forEach(graf => {
    graf._pipeObserver?.disconnect();
    Plotly.purge(graf);
  });
}

function standardAnnotasjoner(graf, original) {
  const layout = graf._fullLayout;
  const width = layout.width;
  const cols = Math.max(1, Math.floor((width - 40) / 250));
  return original.map((annotation, i) => {
    const a = kopi(annotation);
    const px = layout.xaxis.l2p(a.x) + layout.xaxis._offset;
    const py = layout.yaxis.l2p(a.y) + layout.yaxis._offset;
    const cx = 20 + (i % cols + .5) * (width - 40) / cols;
    const cy = 38 + Math.floor(i / cols) * 82;
    return {...a, ax: cx - px, ay: cy - py};
  });
}

// Only visual offsets are clamped. x/y, Q, H, v and tau are never edited.
function begrensAnnotasjoner(graf) {
  const l = graf._fullLayout;
  return (graf.layout.annotations || []).map(a => {
    const px = l.xaxis.l2p(a.x) + l.xaxis._offset;
    const py = l.yaxis.l2p(a.y) + l.yaxis._offset;
    const cx = Math.max(125, Math.min(l.width - 125, px + a.ax));
    const cy = Math.max(38, Math.min(l.height - 50, py + a.ay));
    return {...a, ax: cx - px, ay: cy - py};
  });
}

async function tegnInteraktivGraf(spec, omraade, payload) {
  if (!window.Plotly) throw new Error('Grafbiblioteket kunne ikke lastes. Last siden på nytt.');
  const key = JSON.stringify([spec.id, payload.input, payload.rangering,
    spec.id === 'pris' ? [] : payload.valgte_ror]);
  const figur = document.createElement('figure');
  figur.className = 'graf interaktiv-figur';
  const tittel = document.createElement('figcaption');
  tittel.textContent = spec.tittel;
  const forklaring = document.createElement('p');
  forklaring.className = 'info';
  forklaring.textContent = spec.beskrivelse;
  const hjelp = document.createElement('p');
  hjelp.className = 'info';
  hjelp.textContent = 'Dra i grafen for å panorere. Bruk verktøylinjen for zoom. Klikk på rørnavn for å vise/skjule kurver. Dra tekstbokser for å flytte dem.';
  const verktøy = document.createElement('div');
  verktøy.className = 'grafverktoy';
  const graf = document.createElement('div');
  graf.className = 'interaktiv-graf';
  graf.dataset.grafId = spec.id;
  graf.dataset.tittel = spec.tittel;
  graf.setAttribute('role', 'region');
  graf.setAttribute('aria-label', spec.tittel);
  figur.append(tittel, forklaring, verktøy, graf, hjelp);
  omraade.appendChild(figur);
  const width = Math.max(300, graf.clientWidth);
  const cols = Math.max(1, Math.floor((width - 40) / 250));
  const rows = Math.ceil(spec.layout.annotations.length / cols);
  const top = rows ? rows * 82 + 30 : 30;
  const defaults = kopi(spec.layout);
  defaults.height = 520 + top;
  defaults.margin.t = top;
  // Reserve space below the plot for a wrapped legend, including five or more pipes.
  const pipes = spec.data.filter(t => t.showlegend !== false).length;
  defaults.margin.b = 75 + Math.ceil(pipes / Math.max(1, Math.floor(width / 190))) * 24;
  defaults.height += defaults.margin.b - 100;
  defaults.uirevision = key;
  const saved = grafTilstander.get(key);
  const layout = kopi(saved?.layout || defaults);
  if (!saved?.manual) { layout.height = defaults.height; layout.margin = kopi(defaults.margin); }
  await Plotly.newPlot(graf, kopi(saved?.data || spec.data), layout, {
    responsive: true, displaylogo: false, showSendToCloud: false, scrollZoom: false,
    editable: false, edits: {annotationPosition: false, annotationText: false, annotationTail: true},
    displayModeBar: true, modeBarButtonsToRemove: ['select2d', 'lasso2d', 'toImage'],
  });
  if (!saved?.manual) await Plotly.relayout(graf, {annotations: standardAnnotasjoner(graf, spec.layout.annotations)});
  let endrer = false;
  let manuelle = saved?.manual || false;
  let sisteBredde = graf._fullLayout.width;
  function lagre() {
    grafTilstander.set(key, {data: kopi(graf.data), layout: kopi(graf.layout), manual: manuelle});
    if (grafTilstander.size > 64) grafTilstander.delete(grafTilstander.keys().next().value);
  }
  async function oppdater() {
    if (endrer) return;
    endrer = true;
    try {
      const visible = new Map(graf.data.filter(t => t.showlegend !== false).map(t => [t.legendgroup, t.visible !== 'legendonly' && t.visible !== false]));
      const annotations = begrensAnnotasjoner(graf).map((a, i) => ({...a,
        x: spec.layout.annotations[i].x, y: spec.layout.annotations[i].y,
        visible: visible.get(a.name) !== false}));
      const shapes = (graf.layout.shapes || []).map(s => ({...s, visible: visible.get(s.name) !== false}));
      await Plotly.relayout(graf, {annotations, shapes});
      lagre();
    } finally { endrer = false; }
  }
  graf.on('plotly_relayout', event => {
    if (!endrer && Object.keys(event).some(k => /^annotations\[\d+\]\./.test(k))) manuelle = true;
    oppdater();
  });
  graf.on('plotly_restyle', oppdater);
  const observer = new ResizeObserver(() => {
    if (graf.isConnected) Plotly.Plots.resize(graf).then(async () => {
      const bredde = graf._fullLayout.width;
      if (!manuelle && Math.abs(bredde - sisteBredde) > 1) {
        const nyeRader = Math.ceil(spec.layout.annotations.length / Math.max(1, Math.floor((bredde - 40) / 250)));
        const topp = nyeRader ? nyeRader * 82 + 30 : 30;
        await Plotly.relayout(graf, {'margin.t': topp, height: 520 + topp + defaults.margin.b - 100});
        await Plotly.relayout(graf, {annotations: standardAnnotasjoner(graf, spec.layout.annotations)});
      }
      sisteBredde = bredde;
      await oppdater();
    }).catch(() => {});
  });
  observer.observe(graf);
  graf._pipeObserver = observer;
  lagre();
  const status = document.createElement('span');
  status.className = 'info';
  status.setAttribute('role', 'status');
  function handling(tekst, action) {
    const knapp = document.createElement('button');
    knapp.type = 'button'; knapp.className = 'grafknapp'; knapp.textContent = tekst;
    knapp.addEventListener('click', async () => {
      knapp.disabled = true; status.textContent = '';
      try { await action(); } catch (e) { status.textContent = 'Kunne ikke oppdatere grafen: ' + e.message; }
      finally { knapp.disabled = false; }
    });
    verktøy.appendChild(knapp);
  }
  handling('Tilbakestill zoom', () => Plotly.relayout(graf, {
    'xaxis.range': defaults.xaxis.range, 'xaxis.autorange': !defaults.xaxis.range,
    'yaxis.range': defaults.yaxis.range, 'yaxis.autorange': !defaults.yaxis.range,
  }));
  if (rows) handling('Tilbakestill tekstbokser', () => {
    manuelle = false;
    return Plotly.relayout(graf, {annotations: standardAnnotasjoner(graf, spec.layout.annotations)});
  });
  handling('Last ned SVG', () => Plotly.downloadImage(graf, {format: 'svg', filename: spec.id,
    width: graf._fullLayout.width, height: graf._fullLayout.height}));
  verktøy.appendChild(status);
}

async function eksporterGrafer() {
  const grafer = Array.from(document.querySelectorAll('#resultat .interaktiv-graf'));
  if (!grafer.length) throw new Error('Ingen grafer er klare for eksport.');
  const bilder = [];
  for (const graf of grafer) {
    const bilde = await Plotly.toImage(graf, {format: 'png', scale: 2,
      width: graf._fullLayout.width, height: graf._fullLayout.height});
    bilder.push({id: graf.dataset.grafId, tittel: graf.dataset.tittel, bilde});
  }
  return bilder;
}
