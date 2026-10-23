// Controller tests without a browser. Plotly rendering and pointer input still
// require a real browser; these tests cover our state/placement/export logic.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function runtime(width) {
  const plots = [];
  class Element {
    constructor() { this.children = []; this.dataset = {}; this.clientWidth = width; this.events = {}; this.isConnected = false; }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.append(node); }
    setAttribute() {}
    addEventListener(name, action) { this.events[name] = action; }
    on(name, action) { this.events[name] = action; }
  }
  function update(g) {
    const l = g.layout;
    const w = width - l.margin.l - l.margin.r;
    const h = l.height - l.margin.t - l.margin.b;
    g._fullLayout = {width, height: l.height,
      xaxis: {_offset: l.margin.l, l2p: x => w * (x - l.xaxis.range[0]) / (l.xaxis.range[1] - l.xaxis.range[0])},
      yaxis: {_offset: l.margin.t, l2p: y => h * (1 - (y - l.yaxis.range[0]) / (l.yaxis.range[1] - l.yaxis.range[0]))}};
  }
  const Plotly = {
    async newPlot(g, data, layout, config) { g.data = data; g.layout = layout; g.config = config; plots.push(g); update(g); },
    async relayout(g, patch) {
      for (const [key, value] of Object.entries(patch)) {
        if (key.includes('.')) { const [a,b] = key.split('.'); g.layout[a][b] = value; }
        else g.layout[key] = value;
      }
      update(g);
      g.events.plotly_relayout?.(patch);
    },
    Plots: {async resize(g) {update(g);}},
    async toImage(g, options) { return JSON.stringify({annotations:g.layout.annotations, data:g.data, options}); },
    async downloadImage() {}, purge() {},
  };
  const document = {createElement: () => new Element(), querySelectorAll: () => plots};
  const context = vm.createContext({document, Plotly, window:{Plotly}, ResizeObserver:class {observe(){} disconnect(){}}, console});
  vm.runInContext(fs.readFileSync('static/graphs.js', 'utf8'), context);
  return {context, Plotly, plots, Element};
}

function spec(n) {
  return {id:'samlet', tittel:'Graf', beskrivelse:'Test',
    data:[{legendgroup:'560-17', x:[0,450], y:[0,100]}],
    layout:{margin:{l:76,r:30,t:30,b:100}, xaxis:{range:[0,450]}, yaxis:{range:[0,108]},
      annotations:Array.from({length:n*2},(_,i)=>({x:100+i*10,y:20+i*5,ax:0,ay:-80,name:'560-17'})), shapes:[]}};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

for (const width of [320,768,1120]) for (const pipes of [1,3,5]) {
  test(`Default boxes do not overlap: ${pipes} pipes at ${width}px`, async () => {
    const {context, plots, Element} = runtime(width);
    await context.tegnInteraktivGraf(spec(pipes), new Element(), {input:{q:300}, valgte_ror:[pipes]});
    const g = plots[0];
    assert.equal(g.config.edits.annotationPosition, false);
    assert.equal(g.config.edits.annotationTail, true);
    const centers = g.layout.annotations.map(a=>({x:g._fullLayout.xaxis.l2p(a.x)+g._fullLayout.xaxis._offset+a.ax,
      y:g._fullLayout.yaxis.l2p(a.y)+g._fullLayout.yaxis._offset+a.ay}));
    for (let i=0;i<centers.length;i++) for (let j=i+1;j<centers.length;j++) {
      assert.ok(Math.abs(centers[i].x-centers[j].x)>=240 || Math.abs(centers[i].y-centers[j].y)>=80);
    }
  });
}

test('Moved annotations survive rerender/zoom, export uses current state, new selection resets state', async()=>{
  const {context, plots, Element} = runtime(1120);
  const payload = {input:{q:300}, valgte_ror:[1]};
  await context.tegnInteraktivGraf(spec(1), new Element(), payload);
  const g=plots[0];
  g.layout.annotations[0].ax += 20;
  const offset=g.layout.annotations[0].ax;
  g.events.plotly_relayout({'annotations[0].ax':offset});
  await settle();
  assert.equal(g.layout.annotations[0].x,100);
  assert.equal(g.layout.annotations[0].ax,offset);
  await context.tegnInteraktivGraf(spec(1), new Element(), payload);
  assert.equal(plots[1].layout.annotations[0].ax,offset);
  g.layout.xaxis.range=[0,500];
  g.events.plotly_relayout({'xaxis.range':[0,500]});
  await settle();
  const exported=await context.eksporterGrafer();
  assert.deepEqual(JSON.parse(exported[0].bilde).annotations, JSON.parse(JSON.stringify(g.layout.annotations)));
  await context.tegnInteraktivGraf(spec(1), new Element(), {...payload,valgte_ror:[2]});
  assert.notEqual(plots[2].layout.annotations[0].ax,offset);
});
