// Deterministic controller/workspace tests. This is not a browser renderer.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function runtime(initialWidth = 900) {
  let width = initialWidth;
  const plots = [], downloads = [], images = [];
  let body;
  function matches(node, selector) {
    selector = selector.trim().split(' ').at(-1);
    if (selector.startsWith('.')) return (node.className || '').split(' ').includes(selector.slice(1));
    if (selector.startsWith('#')) return node.id === selector.slice(1);
    const attr=selector.match(/^\[data-([\w-]+)="([^"]+)"\]$/);
    if (attr) return node.dataset[attr[1].replace(/-([a-z])/g,(_,c)=>c.toUpperCase())] === attr[2];
    return node.tag === selector;
  }
  class Element {
    constructor(tag='div') {this.tag=tag;this.children=[];this.dataset={};this.events={};this.attrs={};this.style={setProperty(){}};this.hidden=false;this.textContent='';}
    get clientWidth(){return width;}
    get isConnected(){return this===body || !!this.parent?.isConnected;}
    get lastElementChild(){return this.children.at(-1);}
    append(...nodes){nodes.forEach(n=>{if(typeof n==='string')n=new Element('text');n.remove();n.parent=this;this.children.push(n);});}
    appendChild(node){this.append(node);return node;}
    insertBefore(node,reference){if(!reference){this.append(node);return;}node.remove();node.parent=this;this.children.splice(this.children.indexOf(reference),0,node);}
    replaceChildren(...nodes){this.children.forEach(c=>{c.parent=null;});this.children=[];this.append(...nodes);}
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null;}
    contains(node){return this===node || this.children.some(c=>c.contains(node));}
    setAttribute(k,v){this.attrs[k]=String(v);}
    addEventListener(k,f){this.events[k]=f;}
    on(k,f){this.events[k]=f;}
    querySelectorAll(selector){const result=[];const visit=n=>{for(const child of n.children){if(selector.split(',').some(s=>matches(child,s)))result.push(child);visit(child);}};visit(this);return result;}
    querySelector(s){return this.querySelectorAll(s)[0] || null;}
    focus(){this.focused=true;document.activeElement=this;}
    showModal(){this.open=true;}
    close(){this.open=false;this.events.close?.();}
  }
  body=new Element('body');
  const document={body,createElement:tag=>new Element(tag),createTextNode:text=>{const n=new Element('text');n.textContent=text;return n;},
    querySelectorAll:s=>body.querySelectorAll(s),getElementById:id=>body.querySelector('#'+id)};
  function area(){const n=new Element();n.id='resultat';body.append(n);return n;}
  function update(g) {
    const l=g.layout, w=width-l.margin.l-l.margin.r, h=l.height-l.margin.t-l.margin.b;
    g._fullLayout={width,height:l.height,margin:{...l.margin},
      xaxis:{range:l.xaxis.range,_offset:l.margin.l,l2p:x=>w*(x-l.xaxis.range[0])/(l.xaxis.range[1]-l.xaxis.range[0])},
      yaxis:{range:l.yaxis.range,_offset:l.margin.t,l2p:y=>h*(1-(y-l.yaxis.range[0])/(l.yaxis.range[1]-l.yaxis.range[0]))}};
  }
  const Plotly={
    failId:null,
    async newPlot(g,data,layout,config){if(g.dataset.grafId===this.failId)throw Error('Test render failure');g.data=data;g.layout=layout;g.config=config;plots.push(g);update(g);},
    async relayout(g,patch){for(const[k,v]of Object.entries(patch)){if(k.includes('.')){const[a,b]=k.split('.');g.layout[a][b]=v;}else g.layout[k]=v;}update(g);g.events.plotly_relayout?.(patch);},
    async restyle(g,patch,indices){const target=indices || g.data.map((_,i)=>i);for(const i of target)for(const[k,v]of Object.entries(patch)){const val=Array.isArray(v)&&!indices?v[i]:v;if(val===undefined)continue;if(k.includes('.')){const[a,b]=k.split('.');g.data[i][a]??={};g.data[i][a][b]=val;}else g.data[i][k]=val;}g.events.plotly_restyle?.(patch);},
    Plots:{async resize(g){update(g);}},
    async toImage(figure,options){images.push({figure,options});return JSON.stringify(figure);},
    async downloadImage(figure,options){downloads.push({figure,options});},purge(g){g.purged=true;},
  };
  const context=vm.createContext({document,Plotly,window:{Plotly,innerHeight:920},ResizeObserver:class{observe(){}disconnect(){}},console,API:'',
    rorNavn:r=>`DN${r.dn_od_mm} ${r.sdr_navn}`,lastNedRapport:async()=>{}});
  for(const file of ['graphs.js','analysis.js'])vm.runInContext(fs.readFileSync('static/'+file,'utf8'),context);
  return {context,Plotly,plots,images,downloads,Element,area,body,setWidth:w=>{width=w;}};
}
function spec(n=3,id='samlet',start=0) {
  const data=[],annotations=[],pipes=[];
  for(let i=start;i<start+n;i++){
    const group=`${560+i*10}-17`,label=`DN${560+i*10} SDR 17`,x=100+i*8,y=20+i*3,color='#1764c0';
    const metadata={id:group,label,color,values:{q:300,h:50+i,v:1.8,tau:6.2,price:50+i},points:[]};
    if(id==='pris'){
      metadata.points.push({label:'Dimensjonerende punkt',q:300,h:50+i,v:1.8,tau:6.2,traceIndex:data.length,annotationIndex:null});
      data.push({type:'scatter',mode:'markers',name:label,legendgroup:group,x:[50+i],y:[6.2],marker:{color,size:12},customdata:[[50+i,1.8]]});
    }else{
      data.push({name:label,mode:'lines',legendgroup:group,x:[0,450],y:[0,100],line:{color,width:1.5},opacity:.35,customdata:[[0,0],[3,10]]});
      data.push({name:label,mode:'lines',legendgroup:group,showlegend:false,x:[100,300],y:[20,70],line:{color,width:4.5},customdata:[[1,2],[3,8]]});
      metadata.points.push({label:'τ = 2 Pa',q:x,h:y,v:1.4,tau:2,traceIndex:data.length,annotationIndex:annotations.length});
      data.push({name:label,mode:'markers',legendgroup:group,showlegend:false,x:[x],y:[y],marker:{color,size:7},customdata:[[1.4,2]],text:['τ = 2 Pa']});
      annotations.push({x,y,ax:0,ay:-80,name:group,showarrow:true,text:'Technical values'});
    }
    pipes.push(metadata);
  }
  return {id,tittel:id==='pris'?'Pris mot skjærspenning':'Ledningskarakteristikk',beskrivelse:'Test',data,pipes,layout:{dragmode:'pan',margin:{l:66,r:20,t:30,b:50},xaxis:{range:id==='pris'?[45,70]:[0,450]},yaxis:{range:id==='pris'?[0,8]:[0,108]},annotations,shapes:[{type:'line',x0:0,x1:450,y0:id==='pris'?2:70,y1:id==='pris'?2:70}]},
    thresholdAnnotations:[{name:'hmax',x:1,y:70,showarrow:false,text:'H max = 70 m'}],fullRange:{x:[0,450],y:[0,110]}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const allButtons=root=>root.querySelectorAll('button');
const button=(root,label)=>allButtons(root).find(b=>b.textContent===label || b.attrs['aria-label']===label);
const plain=value=>JSON.parse(JSON.stringify(value));
async function ready(g){await settle();await g._pipeReady();}
async function clickPoint(g,x=100,y=20){await g.events.plotly_click({points:[{x,y,data:g.data[0],customdata:[1.4,2],pointIndex:0}]});}

for(const width of [320,768,1120])for(const count of [1,3,5,10])test(`Integrated defaults ${count} pipes / ${width}px`,async()=>{
  const r=runtime(width),area=r.area();const g=await r.context.tegnInteraktivGraf(spec(count),area,{input:{q:300},valgte_ror:[count]});
  assert.ok(g.layout.height<=470);assert.equal(g.layout.annotations.filter(a=>a.showarrow).length,0);assert.equal(g.layout.annotations[0].text,'H max = 70 m');assert.equal(g.config.displayModeBar,false);
  assert.equal(area.querySelectorAll('.analyse-rorvalg').length,count>1?count:0);
  assert.equal(area.querySelectorAll('input').length,count>=6?1:0);
});

test('Hover/focus are temporary; inspect selection and hiding are distinct; exports are canonical',async()=>{
  const r=runtime(),area=r.area(),s=spec(3);const g=await r.context.tegnInteraktivGraf(s,area,{input:{},valgte_ror:[1]});
  const pick=area.querySelectorAll('.analyse-rorvalg')[1];
  pick.events.mouseenter();await ready(g);assert.ok(g.data[0].opacity<s.data[0].opacity);assert.ok(g.data[3].line.width>s.data[3].line.width);
  let out=r.context.eksportVisning(g);assert.equal(out.data[0].opacity,s.data[0].opacity);assert.equal(out.data[3].line.width,s.data[3].line.width);
  pick.events.mouseleave();await ready(g);assert.equal(g.data[0].opacity,s.data[0].opacity);
  pick.events.focus();await ready(g);assert.ok(area.querySelector('.analyse-verdier'));assert.equal(pick.attrs['aria-pressed'],'false');
  area.querySelector('.analyse-kontekst').events.focusout({relatedTarget:null});await ready(g);assert.equal(pick.attrs['aria-pressed'],'false');
  await pick.events.click();await ready(g);assert.equal(pick.attrs['aria-pressed'],'true');
  await area.querySelectorAll('.analyse-rorsynlighet')[1].events.click();await ready(g);
  assert.equal(g.data[3].visible,'legendonly');assert.equal(pick.attrs['aria-pressed'],'true');
  out=r.context.eksportVisning(g);assert.equal(out.data[3].visible,'legendonly');assert.equal(out.data[0].opacity,s.data[0].opacity);
});

test('Manual positions survive clamping, resize, hide/show and restore; thresholds stay separate',async()=>{
  const r=runtime(),area=r.area(),payload={input:{q:300},valgte_ror:[1]};const g=await r.context.tegnInteraktivGraf(spec(1),area,payload);
  await button(area,'Fest punkt i grafen').events.click();let index=g.layout.annotations.findIndex(a=>a.showarrow);assert.ok(index>=1);
  g.layout.annotations[index].ax+=15;const raw=g.layout.annotations[index].ax;
  g.events.plotly_relayout({[`annotations[${index}].ax`]:raw});await ready(g);
  await r.Plotly.relayout(g,{'xaxis.range':[350,450]});await ready(g);assert.equal(g.layout.annotations.find(a=>a.showarrow).visible,false);
  r.setWidth(400);await g._pipeResize();r.setWidth(900);await g._pipeResize();
  await r.Plotly.relayout(g,{'xaxis.range':[0,450]});await ready(g);assert.ok(Math.abs(g.layout.annotations.find(a=>a.showarrow).ax-raw)<1e-8);
  await button(area,'Skjul tekstbokser').events.click();assert.equal(g.layout.annotations.length,1);
  await button(area,'Vis alle tekstbokser').events.click();assert.ok(Math.abs(g.layout.annotations.find(a=>a.showarrow).ax-raw)<1e-8);
  const exported=r.context.eksportVisning(g);assert.equal(exported.layout.annotations[0].text,'H max = 70 m');assert.ok(Math.abs(exported.layout.annotations.find(a=>a.showarrow).ax-raw)<1e-8);
});

test('Price reference is keyboard pinnable and its inspector uses Q/H rather than scatter axes',async()=>{
  const r=runtime(),area=r.area();const g=await r.context.tegnInteraktivGraf(spec(2,'pris'),area,{input:{qdim_l_s:300},valgte_ror:[]});
  await area.querySelectorAll('.analyse-rorvalg')[0].events.click();
  await button(area,'Fest punkt i grafen').events.click();assert.equal(g.layout.annotations.filter(a=>a.showarrow).length,1);
  await area.querySelector('.analyse-punktvalg').events.click();
  const values=area.querySelectorAll('dd').map(n=>n.textContent);assert.ok(values.includes('300 l/s'));assert.ok(values.includes('50 m'));assert.ok(!values.includes('50 l/s'));
});

test('Arbitrary curve pin retains velocity/shear during later keyboard inspection',async()=>{
  const r=runtime(),area=r.area();const g=await r.context.tegnInteraktivGraf(spec(1),area,{input:{},valgte_ror:[1]});
  await clickPoint(g,175,40);const refs=area.querySelectorAll('.analyse-punktvalg');await refs.at(-1).events.click();
  const values=area.querySelectorAll('dd').map(n=>n.textContent);assert.ok(values.includes('1,4 m/s'));assert.ok(values.includes('2 Pa'));assert.ok(values.includes('175 l/s'));
});

test('Expand uses same graph and preserves zoom; SVG and PDF strip emphasis without live mutations',async()=>{
  const r=runtime(),area=r.area();const g=await r.context.tegnInteraktivGraf(spec(3),area,{input:{},valgte_ror:[1]});
  await r.Plotly.relayout(g,{'xaxis.range':[20,350]});await ready(g);
  await button(area,'Utvid analyse').events.click();assert.equal(r.plots.length,1);assert.ok(r.body.querySelector('dialog').open);
  await button(r.body,'Lukk utvidet analyse').events.click();await ready(g);assert.deepEqual(plain(g.layout.xaxis.range),[20,350]);
  await button(area,'Last ned SVG').events.click();const before=JSON.stringify(g.layout);await r.context.eksporterGrafer();assert.equal(JSON.stringify(g.layout),before);assert.equal(r.downloads[0].figure.layout.showlegend,true);
});

test('Search keeps ten uniquely identified pipes available',async()=>{
  const r=runtime(),area=r.area();await r.context.tegnInteraktivGraf(spec(10),area,{input:{},valgte_ror:[1]});
  const search=area.querySelector('input');search.value='DN650';search.events.input();
  const rows=area.querySelectorAll('.analyse-rorrad');assert.equal(rows.filter(n=>!n.hidden).length,1);search.value='';search.events.input();assert.equal(rows.filter(n=>!n.hidden).length,10);
});

function workspace(r,n=5){
  const price=spec(n,'pris'),combined=spec(n),singles=Array.from({length:n},(_,i)=>spec(1,`ror-${560+i*10}-17`,i));
  r.context.fetch=async(url,options)=>{const p=JSON.parse(options.body);return {ok:true,json:async()=>({grafer:p.vis_prisgraf===false?[combined,...singles]:[price]})};};
  const area=r.area(),result={input:{qdim_l_s:300},rangering:{strategi:'billigste_godkjent'},godkjente:Array.from({length:n},(_,i)=>({dn_od_mm:560+i*10,sdr:17,sdr_navn:'SDR 17'}))};
  return {area,result,price,combined,singles,payload:{input:result.input,rangering:result.rangering}};
}

test('Workspace tabs render lazily, preserve graphs, and export all unvisited individual pipes',async()=>{
  const r=runtime(),w=workspace(r);await r.context.lagAnalyseOmraade(w.payload,w.result);assert.equal(r.plots.length,1);
  const form=w.area.querySelector('form');w.area.querySelectorAll('input').filter(n=>n.type==='checkbox').forEach(cb=>{cb.checked=true;});form.events.change();
  await form.events.submit({preventDefault(){}});assert.equal(r.plots.length,2);assert.equal(w.area.querySelector('.analyse-rapport').hidden,false);
  const combined=r.plots[1];await r.Plotly.relayout(combined,{'xaxis.range':[30,360]});await ready(combined);
  await button(w.area,'Enkeltrør').events.click();await settle();assert.equal(r.plots.length,3);
  await button(w.area,'Sammenligning').events.click();await settle();assert.equal(r.plots.length,3);assert.deepEqual(plain(combined.layout.xaxis.range),[30,360]);
  const before=r.plots.length,exported=await r.context.eksporterGrafer();assert.equal(exported.length,7);assert.equal(r.plots.length,before);
  assert.deepEqual(plain(exported.map(g=>g.id)),['pris','samlet',...w.singles.map(s=>s.id)]);
});

test('Failed comparison rendering leaves report locked',async()=>{
  const r=runtime(),w=workspace(r,1);await r.context.lagAnalyseOmraade(w.payload,w.result);
  const form=w.area.querySelector('form');w.area.querySelectorAll('input').filter(n=>n.type==='checkbox')[0].checked=true;form.events.change();r.Plotly.failId='samlet';
  await form.events.submit({preventDefault(){}});assert.equal(w.area.querySelector('.analyse-rapport').hidden,true);assert.equal(w.area.querySelector('.feilmelding').hidden,false);
});

test('Keyboard pin and reference inspection keep focus on replacement controls',async()=>{
  const r=runtime(),area=r.area();await r.context.tegnInteraktivGraf(spec(1),area,{input:{},valgte_ror:[1]});
  const pin=button(area,'Fest punkt i grafen');pin.focus();await pin.events.click();
  assert.equal(r.context.document.activeElement.dataset.action,'pin');assert.equal(r.context.document.activeElement.attrs['aria-pressed'],'true');
  const reference=area.querySelector('.analyse-punktvalg');reference.focus();await reference.events.click();
  assert.equal(r.context.document.activeElement.dataset.action,'inspect');assert.equal(r.context.document.activeElement.dataset.point,reference.dataset.point);
});

test('Explicit user zoom survives visibility changes; default view can fit visible pipes',async()=>{
  const r=runtime(),area=r.area();const g=await r.context.tegnInteraktivGraf(spec(3),area,{input:{},valgte_ror:[1]});
  await r.Plotly.relayout(g,{'xaxis.range':[30,350],'yaxis.range':[10,80]});await ready(g);
  await area.querySelectorAll('.analyse-rorsynlighet')[0].events.click();
  assert.deepEqual(plain(g.layout.xaxis.range),[30,350]);assert.deepEqual(plain(g.layout.yaxis.range),[10,80]);
  await button(area,'Tilbakestill visning').events.click();assert.deepEqual(plain(g.layout.xaxis.range),[0,450]);assert.equal(g.layout.yaxis.range[0],0);
});
