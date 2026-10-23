/* Presentation state only. Engineering values always come from the API. */
const grafTilstander = new Map();
let analyseEksporter = [];
const kopi = value => JSON.parse(JSON.stringify(value));
const punktId = (group, x, y) => `${group}:${Number(x).toPrecision(12)}:${Number(y).toPrecision(12)}`;
const grafTall = (value, digits = 2) => value == null ? '—' : Number(value).toLocaleString('nb-NO', {maximumFractionDigits: digits});

function grafElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function grafNokkel(spec, payload) {
  return JSON.stringify([spec.id, payload.input, payload.rangering, spec.id === 'pris' ? [] : payload.valgte_ror]);
}

function registrerAnalyseGrafer(specs, payload) {
  analyseEksporter = specs.map(spec => ({spec, payload}));
}

function rensGrafer(omraade) {
  omraade.querySelectorAll('.interaktiv-graf').forEach(graf => {
    graf._pipeObserver?.disconnect();
    graf._pipeDispose?.();
    Plotly.purge(graf);
  });
}

function grafLayout(spec, width, expanded = false) {
  const layout = kopi(spec.layout);
  const narrow = width < 540;
  const ratio = spec.id === 'pris' ? .46 : .56;
  layout.height = expanded ? Math.max(420, window.innerHeight - 180)
    : Math.round(Math.max(narrow ? 300 : 340, Math.min(spec.id === 'pris' ? 400 : 470, width * ratio)));
  layout.margin = {l: narrow ? 58 : 64, r: 20, t: 30, b: 50, autoexpand: false};
  layout.showlegend = false;
  layout.hoverlabel = {bgcolor: '#ffffff', bordercolor: '#dce0e5', font: {family: 'Segoe UI, sans-serif', size: 12, color: '#202327'}, namelength: -1};
  layout.annotations = kopi(spec.thresholdAnnotations || []);
  return layout;
}

function punktPiksler(graf, point) {
  const l = graf._fullLayout;
  return {x: l.xaxis.l2p(point.x) + l.xaxis._offset, y: l.yaxis.l2p(point.y) + l.yaxis._offset};
}

function standardAnnotasjoner(graf, points, obstacles = []) {
  const l = graf._fullLayout;
  const boxes = [...obstacles];
  const anchors = points.map(p => punktPiksler(graf, p));
  return points.map(point => {
    const p = punktPiksler(graf, point);
    let best;
    for (const [dx, dy] of [[112,-58],[-112,-58],[112,58],[-112,58],[0,-108],[0,108],[180,0],[-180,0]]) {
      const x = Math.max(112, Math.min(l.width - 112, p.x + dx));
      const y = Math.max(42, Math.min(l.height - 64, p.y + dy));
      const collisions = boxes.reduce((sum, b) => sum + Math.max(0, 216 - Math.abs(x-b.x)) * Math.max(0, 70-Math.abs(y-b.y)), 0);
      const coversPoint = anchors.reduce((sum, a) => sum + (Math.abs(x-a.x)<108 && Math.abs(y-a.y)<34 ? 1200 : 0), 0);
      const score = collisions + coversPoint + Math.hypot(x-p.x, y-p.y);
      if (!best || score < best.score) best = {x, y, score};
    }
    boxes.push(best);
    return {...point, ax: best.x-p.x, ay: best.y-p.y};
  });
}

// Clamp the displayed box, never the stored user offset or engineering anchor.
function begrensAnnotasjoner(graf, annotations) {
  const l = graf._fullLayout;
  return annotations.map(a => {
    const p = punktPiksler(graf, a);
    const x = Math.max(112, Math.min(l.width-112, p.x+a.ax));
    const y = Math.max(42, Math.min(l.height-64, p.y+a.ay));
    const inView = p.x >= l.margin.l-1 && p.x <= l.width-l.margin.r+1
      && p.y >= l.margin.t-1 && p.y <= l.height-l.margin.b+1;
    return {...a, ax:x-p.x, ay:y-p.y, visible:a.visible !== false && inView};
  });
}

function grafAlternativer(spec) {
  if (spec.pipes) return spec.pipes;
  // Compatibility for older specifications and the controller test fixtures.
  return spec.data.filter(t => t.showlegend !== false).map(t => ({id:t.legendgroup, label:t.name,
    color:t.line?.color || t.marker?.color || '#1764c0', values:{}, points:[]}));
}

function synligUtsnitt(spec, data) {
  const visible=data.filter(t=>t.visible!=='legendonly' && t.visible!==false);
  if (!visible.length) return {x:kopi(spec.layout.xaxis.range),y:kopi(spec.layout.yaxis.range)};
  const limits=(values,pad,zero)=>{
    const low=Math.min(...values), high=Math.max(...values), span=high-low || Math.max(high,1);
    return [zero?0:Math.max(0,low-span*pad),high+span*pad];
  };
  const x=spec.id==='pris'?limits(visible.flatMap(t=>t.x),.12,false):kopi(spec.layout.xaxis.range);
  const thresholds=(spec.layout.shapes||[]).filter(s=>s.y0===s.y1 && s.yref!=='paper').map(s=>s.y0);
  const ys=visible.flatMap(t=>t.y.filter((_,i)=>t.x[i]>=x[0] && t.x[i]<=x[1]));
  return {x,y:limits([...ys,...thresholds,0],.07,true)};
}

async function tegnInteraktivGraf(spec, omraade, payload) {
  if (!window.Plotly) throw new Error('Grafbiblioteket kunne ikke lastes. Last siden på nytt.');
  const key = grafNokkel(spec, payload);
  const saved = grafTilstander.get(key);
  const pipes = grafAlternativer(spec);
  const canonical = kopi(spec.data);
  const points = kopi(saved?.points || (spec.layout.annotations || []).map(a => ({...a, group:a.name, name:punktId(a.name,a.x,a.y)})));
  const pins = new Set(saved?.pins || []);
  const placements = new Map(saved?.placements || []);
  let userZoom = saved?.userZoom || false;
  let selected = saved?.selected || (pipes.length === 1 ? pipes[0].id : null);
  let inspected = null;
  let hovered = null;
  let focusGroup = null;
  let internalLayout = false;
  let internalStyle = false;
  let disposed = false;
  let expanded = false;
  let syncQueue = Promise.resolve();
  let styleQueue = Promise.resolve();
  let renderingDetails = false;
  if (spec.id==='pris' && !saved) pipes.forEach(pipe=>{
    const trace=canonical.find(t=>t.legendgroup===pipe.id);
    const v=pipe.values;
    if (!trace) return;
    points.push({name:punktId(pipe.id,trace.x[0],trace.y[0]),group:pipe.id,x:trace.x[0],y:trace.y[0],detail:{...v,label:'Dimensjonerende punkt'},
      xref:'x',yref:'y',axref:'pixel',ayref:'pixel',showarrow:true,arrowhead:0,arrowcolor:pipe.color,bgcolor:'white',borderwidth:1,xanchor:'center',yanchor:'middle',align:'left',
      text:`<b>${pipe.label}</b><br>Pris ${grafTall(v.price)} MNOK · τ ${grafTall(v.tau,3)} Pa<br>H ${grafTall(v.h)} m · v ${grafTall(v.v,3)} m/s`});
  });

  const figur = grafElement('figure', 'analyse-figur');
  const header = grafElement('div', 'analyse-grafhode');
  const intro = grafElement('div', 'analyse-grafintro');
  intro.append(grafElement('figcaption', '', spec.tittel), grafElement('p', 'info', spec.beskrivelse));
  const tools = grafElement('div', 'grafverktoy');
  tools.setAttribute('role', 'group'); tools.setAttribute('aria-label', 'Grafverktøy');
  header.append(intro, tools);
  const body = grafElement('div', 'analyse-kropp');
  const surface = grafElement('div', 'analyse-plotflate');
  const graf = grafElement('div', 'interaktiv-graf');
  graf.dataset.grafId = spec.id; graf.dataset.tittel = spec.tittel;
  graf.setAttribute('role', 'region'); graf.setAttribute('aria-label', spec.tittel);
  surface.appendChild(graf);
  const panel = grafElement('aside', 'analyse-kontekst');
  if (pipes.length===1) panel.className+=' analyse-kontekst-enkel';
  panel.setAttribute('aria-label', 'Røralternativer og tekniske verdier');
  const list = grafElement('div', 'analyse-rorliste');
  const details = grafElement('div', 'analyse-inspektor');
  const status = grafElement('span', 'grafstatus'); status.setAttribute('role', 'status');
  body.append(surface, panel); figur.append(header, body, status); omraade.appendChild(figur);

  const width = Math.max(280, graf.clientWidth);
  const defaults = grafLayout(spec, width);
  const layout = {...kopi(saved?.layout || defaults), height:defaults.height, margin:defaults.margin, showlegend:false, uirevision:key};
  const data = canonical.map((t,i) => ({...kopi(t), visible:saved?.data?.[i]?.visible ?? t.visible}));
  await Plotly.newPlot(graf, data, layout, {responsive:true, displaylogo:false, displayModeBar:false,
    showSendToCloud:false, scrollZoom:false, editable:false,
    edits:{annotationPosition:false, annotationText:false, annotationTail:true}});
  graf._pipeSpec = spec;
  graf._pipeKey = key;

  function visibleGroups() {
    return new Map(graf.data.filter(t => t.showlegend !== false).map(t => [t.legendgroup, t.visible !== 'legendonly' && t.visible !== false]));
  }
  function canonicalData() {
    return canonical.map((t,i) => ({...kopi(t), visible:graf.data[i].visible ?? t.visible}));
  }
  function save() {
    grafTilstander.set(key, {data:canonicalData(), layout:kopi(graf.layout), points:kopi(points), pins:[...pins], placements:[...placements], selected,
      userZoom,size:{width:graf._fullLayout.width,height:graf._fullLayout.height}});
    if (grafTilstander.size > 64) grafTilstander.delete(grafTilstander.keys().next().value);
  }
  function applyEmphasis() {
    styleQueue = styleQueue.then(async () => {
      if (disposed) return;
      const group = hovered || focusGroup || selected;
      internalStyle = true;
      try {
        await Plotly.restyle(graf, {
          opacity:canonical.map(t => (t.opacity ?? 1) * (group && t.legendgroup !== group ? .28 : 1)),
          'line.width':canonical.map(t => t.line ? t.line.width + (group === t.legendgroup ? 1 : 0) : undefined),
          zorder:canonical.map(t => group === t.legendgroup ? 3 : (t.zorder || 0)),
        });
      } finally { internalStyle = false; }
    });
    return styleQueue;
  }
  async function synchronize() {
    if (disposed) return;
    const visibility = visibleGroups();
    const active = points.filter(p => pins.has(p.name));
    const manual = active.filter(p => placements.has(p.name));
    const obstacles = manual.map(p => {
      const pos = placements.get(p.name), anchor = punktPiksler(graf,p);
      return {x:anchor.x+pos.ax, y:anchor.y+pos.ay};
    });
    const autos = new Map(standardAnnotasjoner(graf, active.filter(p => !placements.has(p.name)), obstacles).map(a => [a.name,a]));
    const plotWidth = graf._fullLayout.width - graf._fullLayout.margin.l - graf._fullLayout.margin.r;
    const plotHeight = graf._fullLayout.height - graf._fullLayout.margin.t - graf._fullLayout.margin.b;
    const annotations = active.map(p => {
      const {group, detail, ...base} = p;
      const manual = placements.get(p.name);
      const offset = manual ? {ax:manual.ax * plotWidth/manual.width, ay:manual.ay * plotHeight/manual.height} : autos.get(p.name);
      return {...base, ax:offset.ax, ay:offset.ay, visible:visibility.get(group) !== false,
        borderpad:6, font:{size:11,color:'#202327'}, arrowwidth:.8, bordercolor:'#dce0e5'};
    });
    const thresholds = kopi(spec.thresholdAnnotations || []);
    const shapes = (spec.layout.shapes || []).map(s => ({...s, visible:visibility.get(s.name) !== false}));
    internalLayout = true;
    try { await Plotly.relayout(graf, {annotations:[...thresholds,...begrensAnnotasjoner(graf, annotations)], shapes}); }
    finally { internalLayout = false; }
    list.querySelectorAll('[data-role="visibility"]').forEach(b => {
      const visible=visibility.get(b.dataset.group)!==false;
      b.setAttribute('aria-pressed',String(visible)); b.textContent=visible?'Skjul':'Vis';
    });
    list.querySelectorAll('[data-role="inspect"]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.group === selected)));
    save();
  }
  function sync() {
    syncQueue = syncQueue.then(synchronize).catch(error => {status.textContent = 'Grafen kunne ikke oppdateres: ' + error.message;});
    return syncQueue;
  }
  async function fitVisible() {
    const range=synligUtsnitt(spec,canonicalData());
    internalLayout=true;
    try {await Plotly.relayout(graf,{'xaxis.range':range.x,'yaxis.range':range.y,'xaxis.autorange':false,'yaxis.autorange':false});}
    finally {internalLayout=false;}
    await sync();
  }
  async function toggleGroup(id) {
    const indices=graf.data.flatMap((t,i)=>t.legendgroup===id?[i]:[]);
    internalStyle=true;
    try {await Plotly.restyle(graf,{visible:visibleGroups().get(id)?'legendonly':true},indices);}
    finally {internalStyle=false;}
    if (!userZoom) await fitVisible();
    await sync(); renderDetails();
  }
  function button(parent, text, label, action, className = 'grafknapp') {
    const b = grafElement('button', className, text); b.type = 'button'; b.title = label; b.setAttribute('aria-label',label);
    let pending=false;
    b.addEventListener('click', async () => {
      if (pending) return;
      pending=true; b.setAttribute('aria-disabled','true'); status.textContent = '';
      try { await action(b); } catch(e) { status.textContent = 'Kunne ikke oppdatere grafen: ' + e.message; }
      finally { pending=false; b.setAttribute('aria-disabled','false'); }
    });
    parent.appendChild(b); return b;
  }
  function inspect(id, point = null) {
    selected = id; inspected = point; renderDetails(); save();
    list.querySelectorAll('[data-role="inspect"]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.group === selected)));
    return applyEmphasis();
  }
  async function togglePin(point) {
    pins.has(point.name) ? pins.delete(point.name) : pins.add(point.name);
    await sync(); renderDetails();
    status.textContent = pins.size ? `${pins.size} punkter festet` : 'Ingen festede punkter';
  }
  function renderDetails() {
    if (renderingDetails) return;
    renderingDetails=true;
    const focused=document.activeElement;
    const restore=details.contains(focused) && focused.dataset.point ? {point:focused.dataset.point,action:focused.dataset.action} : null;
    details.replaceChildren();
    const pipe = pipes.find(p => p.id === (focusGroup || selected));
    if (!pipe) {
      details.append(grafElement('p','analyse-inspektor-tom','Velg et rør for nøkkeltall og referansepunkter.'));
      renderingDetails=false;
      return;
    }
    const currentPoint=(!focusGroup || focusGroup===selected)?inspected:null;
    details.append(grafElement('p','analyse-overlinje',currentPoint ? currentPoint.label || 'Valgt punkt' : 'Ved dimensjonerende vannmengde'));
    details.append(grafElement('h4','',pipe.label));
    const values = currentPoint ? {q:currentPoint.q,h:currentPoint.h,v:currentPoint.v,tau:currentPoint.tau,price:pipe.values.price} : pipe.values;
    const dl = grafElement('dl','analyse-verdier');
    for (const [label,value,unit,digits] of [['Vannmengde',values.q,'l/s',1],['Totalt tap',values.h,'m',2],['Hastighet',values.v,'m/s',3],['Skjærspenning',values.tau,'Pa',3],['Kostnad',values.price,'MNOK',2]]) {
      const row = grafElement('div'); row.append(grafElement('dt','',label),grafElement('dd','',`${grafTall(value,digits)} ${unit}`)); dl.appendChild(row);
    }
    details.appendChild(dl);
    if (visibleGroups().get(pipe.id) === false) details.append(grafElement('p','info','Dette røret er skjult i grafen.'));
    const refs = points.filter(p => p.group === pipe.id);
    if (refs.length) {
      details.append(grafElement('p','analyse-overlinje','Referansepunkter'));
      const refList = grafElement('div','analyse-referanser');
      refs.forEach(p => {
        const metadata = p.detail || pipe.points.find(ref => Math.abs(ref.q-p.x)<1e-7 && Math.abs(ref.h-p.y)<1e-7)
          || (spec.id==='pris'?{...pipe.values,label:'Qdim'}:null);
        const label = metadata?.label || 'Valgt punkt';
        const row = grafElement('div','analyse-referanse');
        const inspectButton=button(row,`${label} · ${grafTall(metadata?.q ?? p.x,1)} l/s`,'Inspiser ' + label,() => inspect(pipe.id,metadata || {label,q:p.x,h:p.y,v:null,tau:null}),'analyse-punktvalg');
        inspectButton.dataset.point=p.name;inspectButton.dataset.action='inspect';
        const pin = button(row,pins.has(p.name)?'−':'+',pins.has(p.name)?'Fjern festet punkt':'Fest punkt i grafen',() => togglePin(p),'analyse-punktfest');
        pin.dataset.point=p.name;pin.dataset.action='pin';
        pin.setAttribute('aria-pressed',String(pins.has(p.name))); refList.appendChild(row);
      });
      details.appendChild(refList);
    }
    renderingDetails=false;
    if (restore) [...details.querySelectorAll('button')].find(b=>b.dataset.point===restore.point && b.dataset.action===restore.action)?.focus();
  }

  if (pipes.length > 1) {
    const contextHeader = grafElement('div','analyse-listehode');
    contextHeader.append(grafElement('h4','','Røralternativer'),grafElement('span','analyse-antall',String(pipes.length)));
    button(contextHeader,'×','Opphev rørvalg',() => {selected=null;focusGroup=null;inspected=null;renderDetails();save();return applyEmphasis();});
    panel.appendChild(contextHeader);
    if (pipes.length >= 6) {
      const search = grafElement('input','analyse-sok'); search.type='search'; search.placeholder='Finn DN eller SDR'; search.setAttribute('aria-label','Søk i røralternativer');
      search.addEventListener('input',() => {
        const query=search.value.trim().toLocaleLowerCase('nb-NO').replaceAll(',','.');
        list.querySelectorAll('.analyse-rorrad').forEach(row => {row.hidden=!row.dataset.label.replaceAll(',','.').includes(query);});
      }); panel.appendChild(search);
    }
    panel.appendChild(list);
    pipes.forEach(pipe => {
      const row = grafElement('div','analyse-rorrad'); row.dataset.label=pipe.label.toLocaleLowerCase('nb-NO');
      const pick = button(row,pipe.label,'Inspiser '+pipe.label,() => inspect(pipe.id),'analyse-rorvalg');
      pick.dataset.role='inspect'; pick.dataset.group=pipe.id; pick.style.setProperty('--kurvefarge',pipe.color);
      pick.setAttribute('aria-pressed',String(selected===pipe.id));
      pick.addEventListener('mouseenter',() => {hovered=pipe.id; applyEmphasis();});
      pick.addEventListener('mouseleave',() => {hovered=null; applyEmphasis();});
      pick.addEventListener('focus',() => {focusGroup=pipe.id;renderDetails();applyEmphasis();});
      const show = button(row,'Skjul','Vis eller skjul '+pipe.label,() => toggleGroup(pipe.id),'analyse-rorsynlighet');
      show.dataset.role='visibility'; show.dataset.group=pipe.id;
      show.setAttribute('aria-pressed',String(visibleGroups().get(pipe.id)!==false)); list.appendChild(row);
    });
  }
  panel.appendChild(details); renderDetails();
  panel.addEventListener('focusout',event => {
    if (renderingDetails) return;
    if (!panel.contains(event.relatedTarget)) {focusGroup=null;renderDetails();applyEmphasis();}
  });

  graf.on('plotly_relayout', event => {
    if (internalLayout || disposed) return;
    if (Object.keys(event).some(k=>k.startsWith('xaxis.') || k.startsWith('yaxis.'))) userZoom=true;
    Object.keys(event).forEach(k => {
      const match=k.match(/^annotations\[(\d+)\]\./);
      const a=match && graf.layout.annotations[Number(match[1])];
      if (a && pins.has(a.name)) placements.set(a.name,{ax:a.ax,ay:a.ay,
        width:graf._fullLayout.width-graf._fullLayout.margin.l-graf._fullLayout.margin.r,
        height:graf._fullLayout.height-graf._fullLayout.margin.t-graf._fullLayout.margin.b});
    });
    sync();
  });
  graf.on('plotly_restyle',() => {if (!internalStyle) sync();});
  graf.on('plotly_click',async event => {
    const p=event.points?.[0]; if (!p) return;
    const group=p.data.legendgroup;
    const id=punktId(group,p.x,p.y);
    const c=p.customdata || p.data.customdata?.[p.pointIndex]; if (!c) return;
    const pipe=pipes.find(a => a.id===group);
    const detail=spec.id==='pris' ? {label:'Dimensjonerende punkt',q:pipe?.values.q,h:c[0],v:c[1],tau:p.y}
      : {label:p.text || 'Valgt kurvepunkt',q:p.x,h:p.y,v:c[0],tau:c[1]};
    if (!points.some(a=>a.name===id)) {
      const text=spec.id==='pris' ? `<b>${p.data.name}</b><br>Pris ${grafTall(p.x)} MNOK · τ ${grafTall(p.y,3)} Pa<br>H ${grafTall(c[0])} m · v ${grafTall(c[1],3)} m/s`
        : `<b>${p.data.name}</b><br>Q ${grafTall(p.x,1)} l/s · H ${grafTall(p.y)} m<br>v ${grafTall(c[0],3)} m/s · τ ${grafTall(c[1],3)} Pa`;
      points.push({name:id,group,x:p.x,y:p.y,xref:'x',yref:'y',axref:'pixel',ayref:'pixel',showarrow:true,arrowhead:0,
        arrowcolor:pipe?.color || '#616973',bgcolor:'white',borderwidth:1,xanchor:'center',yanchor:'middle',align:'left',text});
    }
    const point=points.find(a=>a.name===id); point.detail=detail;
    await inspect(group,detail); await togglePin(point);
  });

  function zoom(factor) {
    const patch={};
    for (const axis of ['xaxis','yaxis']) {
      const [a,b]=graf._fullLayout[axis].range;
      const mid=(a+b)/2,half=(b-a)*factor/2;
      patch[`${axis}.range`]=[mid-half,mid+half]; patch[`${axis}.autorange`]=false;
    }
    return Plotly.relayout(graf,patch);
  }
  button(tools,'↺','Tilbakestill visning',async () => {userZoom=false;await fitVisible();});
  const mode=button(tools,'Zoom','Velg et område for å zoome',async b => {
    const active=graf.layout.dragmode!=='zoom'; await Plotly.relayout(graf,{dragmode:active?'zoom':'pan'}); b.setAttribute('aria-pressed',String(active));
  }); mode.setAttribute('aria-pressed',String(graf.layout.dragmode==='zoom'));
  let dialog;
  const expand=button(tools,'⤢','Utvid analyse',async () => {
    if (expanded) {dialog.close(); return;}
    dialog=grafElement('dialog','analyse-dialog');
    dialog.setAttribute('aria-label',spec.tittel+' – utvidet analyse'); document.body.appendChild(dialog);
    dialog.appendChild(figur); expanded=true; dialog.showModal();
    expand.textContent='×'; expand.title='Lukk utvidet analyse'; expand.setAttribute('aria-label','Lukk utvidet analyse');
    dialog.addEventListener('close',async () => {
      omraade.appendChild(figur); dialog.remove(); expanded=false;
      expand.textContent='⤢';expand.title='Utvid analyse';expand.setAttribute('aria-label','Utvid analyse');
      await resize(); expand.focus();
    },{once:true});
    await resize();
  });
  const menu=grafElement('details','grafmeny');
  menu.appendChild(grafElement('summary','','Valg'));
  const options=grafElement('div','grafmeny-innhold'); menu.appendChild(options); tools.appendChild(menu);
  button(options,'Zoom inn','Zoom inn',() => zoom(.8));
  button(options,'Zoom ut','Zoom ut',() => zoom(1.25));
  button(options,'Vis hele kurven','Vis hele det beregnede kurveområdet',() => Plotly.relayout(graf,{
    'xaxis.range':spec.fullRange?.x || defaults.xaxis.range,'xaxis.autorange':!defaults.xaxis.range,
    'yaxis.range':spec.fullRange?.y || defaults.yaxis.range,'yaxis.autorange':!defaults.yaxis.range}));
  button(options,'Vis alle tekstbokser','Fest alle referansepunkter',async () => {points.forEach(p=>pins.add(p.name)); await sync(); renderDetails();});
  button(options,'Skjul tekstbokser','Skjul bokser og behold deres plassering',async () => {pins.clear(); await sync(); renderDetails();});
  button(options,'Tilbakestill plassering','Tilbakestill de festede tekstboksene',async () => {placements.clear(); await sync();});
  if (pipes.length===1) button(options,'Vis/skjul kurven','Vis eller skjul dette røret',()=>toggleGroup(pipes[0].id));
  button(options,'Last ned SVG','Eksporter denne visningen som SVG',async () => {
    await syncQueue; await styleQueue;
    const figure=eksportVisning(graf);
    return Plotly.downloadImage(figure,{format:'svg',filename:spec.id,width:figure.layout.width,height:figure.layout.height});
  });
  options.appendChild(grafElement('p','info','Dra for å panorere. Velg Zoom for områdemarkering. Klikk på et punkt for å feste/fjerne en boks. Rørnavn inspiserer; Vis/Skjul-knappen styrer synlighet.'));
  async function resize() {
    if (disposed || !graf.isConnected || omraade.hidden) return;
    await Plotly.Plots.resize(graf);
    const target=grafLayout(spec,graf._fullLayout.width,expanded);
    internalLayout=true;
    try {await Plotly.relayout(graf,{height:target.height,margin:target.margin});}
    finally {internalLayout=false;}
    await sync();
  }
  const observer=new ResizeObserver(() => {resize().catch(()=>{});}); observer.observe(surface);
  graf._pipeObserver=observer;
  graf._pipeResize=resize;
  graf._pipeDispose=() => {disposed=true; if (dialog?.open) dialog.close();};
  graf._pipeReady=async () => {await syncQueue; await styleQueue;};
  graf._pipeCanonical=canonicalData;
  await sync(); await applyEmphasis();
  return graf;
}

function eksportVisning(graf) {
  const state= graf._pipeKey ? grafTilstander.get(graf._pipeKey) : null;
  const layout=kopi(state?.layout || graf.layout);
  const data=graf._pipeCanonical ? graf._pipeCanonical() : kopi(graf.data);
  // Emphasis and HTML controls are transient; exports retain engineering styles.
  layout.showlegend=true;
  layout.legend={...layout.legend,orientation:'h',x:0,y:-.16,font:{size:10},groupclick:'togglegroup'};
  const width=graf._fullLayout.width;
  const count=data.filter(t=>t.showlegend!==false).length;
  const extra=32+Math.ceil(count/Math.max(1,Math.floor(width/180)))*22;
  layout.width=width; layout.height=graf._fullLayout.height+extra; layout.margin.b+=extra;
  return {data,layout};
}

async function eksporterGrafer() {
  const bilder=[];
  const live=Array.from(document.querySelectorAll('#resultat .interaktiv-graf, .analyse-dialog .interaktiv-graf')).filter(g=>g._fullLayout && g.data);
  const entries=analyseEksporter.length ? analyseEksporter : live.map(graf=>({graf}));
  for (const entry of entries) {
    const graf=entry.graf || live.find(g=>g.dataset.grafId===entry.spec.id);
    let figure;
    if (graf) {await graf._pipeReady?.(); figure=eksportVisning(graf);}
    else {
      const saved=grafTilstander.get(grafNokkel(entry.spec,entry.payload));
      const width=saved?.size?.width || live[0]?._fullLayout.width || 900;
      const layout=kopi(saved?.layout || grafLayout(entry.spec,width));
      if (!saved) layout.annotations=kopi(entry.spec.thresholdAnnotations || []);
      const dummy={data:kopi(saved?.data || entry.spec.data),layout,_fullLayout:{width,height:layout.height}};
      figure=eksportVisning(dummy);
    }
    const bilde=await Plotly.toImage(figure,{format:'png',scale:2,width:figure.layout.width,height:figure.layout.height});
    bilder.push({id:entry.spec?.id || graf.dataset.grafId,tittel:entry.spec?.tittel || graf.dataset.tittel,bilde});
  }
  return bilder;
}
