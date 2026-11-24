const assert=require('node:assert/strict');
const {layout}=require('../web/graph.js');
const nodes=[{id:'0'},{id:'1'},{id:'2'}],edges=[{source:'0',target:'1'},{source:'1',target:'2'},{source:'1',target:'1'}];
const first=layout(nodes,edges),second=layout(nodes,edges);
assert.deepEqual([...first],[...second]);
for(const point of first.values()){assert.ok(Number.isFinite(point.x)&&Number.isFinite(point.y));assert.ok(point.x>=65&&point.x<=635);}
assert.equal(layout([],[]).size,0);
assert.deepEqual(layout([{id:'0'}],[]).get('0'),{x:350,y:220});
console.log('Graph layout checks passed');
