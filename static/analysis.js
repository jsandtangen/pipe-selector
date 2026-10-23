/* One analysis workspace. Specifications remain available for lazy rendering/export. */
async function lagAnalyseOmraade(payload, resultat) {
  const root = grafElement('section', 'analyse');
  root.setAttribute('aria-labelledby', 'analyse-tittel');
  const intro = grafElement('div', 'analyse-introduksjon');
  const heading = grafElement('div');
  heading.append(grafElement('p', 'overlinje', 'Analyse'), grafElement('h3', '', 'Utforsk alternativene'));
  heading.lastElementChild.id = 'analyse-tittel';
  intro.append(heading, grafElement('p', 'info', 'Kostnad, hydraulikk og referansepunkter. Ett arbeidsområde.'));
  root.appendChild(intro);
  const resultArea=document.getElementById('resultat');
  resultArea.insertBefore(root,resultArea.querySelector('.kort, .underkjente'));

  const selection = grafElement('details', 'analyse-utvalg');
  const selectionSummary = grafElement('summary', '', 'Velg rør til sammenligning');
  selection.open = true;
  const form = grafElement('form', 'grafvalg');
  const fieldset = document.createElement('fieldset');
  fieldset.appendChild(grafElement('legend', '', 'Godkjente rør'));
  const options = grafElement('div', 'analyse-utvalgsliste');
  const checkboxes = resultat.godkjente.map((pipe, index) => {
    const label = grafElement('label');
    const input = document.createElement('input'); input.type = 'checkbox'; input.value = String(index);
    label.append(input, document.createTextNode(rorNavn(pipe))); options.appendChild(label);
    return input;
  });
  fieldset.appendChild(options);
  const selectionActions = grafElement('div', 'grafvalg-handlinger');
  const plot = grafElement('button', '', 'Plott valgte rør'); plot.type = 'submit'; plot.disabled = true;
  const count = grafElement('span', 'info', '0 rør valgt'); count.setAttribute('role', 'status');
  selectionActions.append(plot, count); form.append(fieldset, selectionActions);
  selection.append(selectionSummary, form);
  if (checkboxes.length) root.appendChild(selection);

  const report = grafElement('section', 'rapport-panel analyse-rapport'); report.hidden = true;
  report.setAttribute('aria-label', 'Last ned sammenligningen');
  const reportText = grafElement('div');
  reportText.append(grafElement('h4', '', 'Ta med analysen videre'), grafElement('p', '', 'PDF med beregningsgrunnlag, valgte grafer og referanseverdier.'));
  const download = grafElement('button', '', 'Last ned rapport'); download.type = 'button';
  const reportStatus = grafElement('span', 'rapport-status'); reportStatus.setAttribute('role', 'status');
  report.append(reportText, download, reportStatus); root.appendChild(report);

  const workspace = grafElement('div', 'analyse-arbeidsflate');
  const nav = grafElement('div', 'analyse-navigasjon');
  const tabs = grafElement('div', 'analyse-faner'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'Analysevisning');
  const view = grafElement('div', 'analyse-viewport'); view.id = 'analyse-visning'; view.setAttribute('role', 'tabpanel');
  const single = grafElement('div', 'analyse-enkelvalg'); single.hidden = true;
  const singleLabel = grafElement('label', '', 'Vis rør'); singleLabel.htmlFor = 'analyse-enkeltror';
  const singleSelect = document.createElement('select'); singleSelect.id = 'analyse-enkeltror'; single.append(singleLabel, singleSelect);
  const error = grafElement('p', 'feilmelding'); error.hidden = true; error.setAttribute('role', 'alert');
  nav.append(tabs, single); workspace.append(nav, view, error); root.appendChild(workspace);
  const tabNames = [['pris','Pris'],['samlet','Sammenligning'],['enkel','Enkeltrør']];
  const tabButtons = new Map();
  const entries = new Map();
  let priceSpec = null;
  let curveSpecs = [];
  let active = 'pris';
  let requestVersion = 0;
  let plottedSelection = [];

  function selectedPipes() {
    return checkboxes.filter(cb => cb.checked).map(cb => {
      const r = resultat.godkjente[Number(cb.value)];
      return {dn_od_mm:r.dn_od_mm, sdr:r.sdr};
    });
  }
  async function fetchSpecs(body) {
    const response = await fetch(`${API}/api/calculations/interactive-plots`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Grafdata kunne ikke lastes.');
    return data.grafer;
  }
  function register() {
    registrerAnalyseGrafer([...(priceSpec ? [priceSpec] : []),...curveSpecs], {...payload,valgte_ror:plottedSelection});
    tabButtons.get('samlet').disabled = !curveSpecs.length;
    tabButtons.get('enkel').disabled = !curveSpecs.length;
  }
  function addEntry(spec, body) {
    const host = grafElement('div', 'analyse-grafpanel'); host.hidden = true;
    view.appendChild(host); entries.set(spec.id,{spec,body,host,graph:null,pending:null});
  }
  async function show(category) {
    const version = ++requestVersion;
    active = category;
    const id = category === 'enkel' ? singleSelect.value : category;
    const entry = entries.get(id);
    if (!entry) return;
    error.hidden = true;
    single.hidden = category !== 'enkel';
    tabButtons.forEach((b,key) => {b.setAttribute('aria-selected',String(key===category)); b.tabIndex = key===category ? 0 : -1;});
    view.setAttribute('aria-labelledby', 'analyse-fane-'+category);
    entries.forEach(e => {e.host.hidden = e!==entry;});
    view.setAttribute('aria-busy','true');
    try {
      if (!entry.pending) {
        rensGrafer(entry.host); entry.host.replaceChildren();
        entry.pending = tegnInteraktivGraf(entry.spec,entry.host,entry.body).then(graph => {entry.graph=graph;return graph;}).catch(e => {entry.pending=null;throw e;});
      }
      await entry.pending;
      if (version !== requestVersion) return;
      await entry.graph._pipeResize();
      return true;
    } catch (e) {if(version===requestVersion){error.textContent='Grafen kunne ikke vises: '+e.message;error.hidden=false;}return false;}
    finally {if(version===requestVersion)view.setAttribute('aria-busy','false');}
  }
  tabNames.forEach(([key,label]) => {
    const b = grafElement('button', '', label); b.type='button'; b.id='analyse-fane-'+key;
    b.setAttribute('role','tab'); b.setAttribute('aria-controls',view.id); b.setAttribute('aria-selected',String(key==='pris')); b.tabIndex=key==='pris'?0:-1;
    b.disabled=key!=='pris'; b.addEventListener('click',()=>show(key));
    b.addEventListener('keydown',event => {
      if (!['ArrowRight','ArrowLeft','Home','End'].includes(event.key)) return;
      event.preventDefault(); const enabled=[...tabButtons.values()].filter(t=>!t.disabled); const i=enabled.indexOf(b);
      const next=event.key==='Home'?enabled[0]:event.key==='End'?enabled.at(-1):enabled[(i+(event.key==='ArrowRight'?1:-1)+enabled.length)%enabled.length];
      next.focus(); const target=[...tabButtons].find(([,value])=>value===next)[0]; show(target);
    }); tabs.appendChild(b); tabButtons.set(key,b);
  });
  singleSelect.addEventListener('change',()=>show('enkel'));
  function clearCurves() {
    [...entries].filter(([id])=>id!=='pris').forEach(([id,e])=>{rensGrafer(e.host); e.host.remove();entries.delete(id);});
    curveSpecs=[];plottedSelection=[];singleSelect.replaceChildren();register();
  }
  form.addEventListener('change',()=>{
    const selected=selectedPipes();plot.disabled=!selected.length || !priceSpec;
    count.textContent=`${selected.length} rør valgt`;report.hidden=true;reportStatus.textContent='';
    clearCurves(); if (active!=='pris') show('pris');
  });
  form.addEventListener('submit',async event => {
    event.preventDefault(); const selected=selectedPipes();if(!selected.length)return;
    plot.disabled=true;fieldset.disabled=true;plot.textContent='Plotter …';report.hidden=true;
    try {
      clearCurves();
      const body={...payload,valgte_ror:selected,vis_prisgraf:false};
      curveSpecs=await fetchSpecs(body);plottedSelection=selected;
      curveSpecs.forEach(spec=>{
        addEntry(spec,body);
        if(spec.id!=='samlet') {const option=grafElement('option','',spec.pipes?.[0]?.label||spec.tittel);option.value=spec.id;singleSelect.appendChild(option);}
      });
      singleSelect.value=curveSpecs.find(spec=>spec.id!=='samlet')?.id || '';
      register(); const rendered=await show('samlet');
      report.hidden=!(rendered && priceSpec); selection.open=!rendered; selectionSummary.textContent=`${selected.length} rør i sammenligningen · Endre utvalg`;
      if (rendered) tabButtons.get('samlet').focus();
    } catch(e) {error.textContent='Sammenligningen kunne ikke lastes: '+e.message;error.hidden=false;}
    finally {plot.disabled=false;fieldset.disabled=false;plot.textContent='Plott valgte rør';}
  });
  download.addEventListener('click',()=>lastNedRapport({input:resultat.input,rangering:resultat.rangering,valgte_ror:plottedSelection},download,reportStatus));
  try {
    priceSpec=(await fetchSpecs({...payload,valgte_ror:[]}))[0];
    addEntry(priceSpec,{...payload,valgte_ror:[]});register();await show('pris');
    plot.disabled=!selectedPipes().length;
  } catch(e) {error.textContent='Grafene kunne ikke vises: '+e.message;error.hidden=false;}
}
