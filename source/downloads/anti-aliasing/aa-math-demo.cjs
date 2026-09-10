'use strict';
// CPU illustration: not a rasterizer, UE plugin, or GPU timing test.
const assert = require('node:assert/strict');
const near = (a,b) => assert.ok(Math.abs(a-b)<1e-9, `${a} != ${b}`);
const average = samples => samples[0].map((_,c)=>samples.reduce((sum,v)=>sum+v[c],0)/samples.length);
const bg=[1,1,1], a=[1,.8,.2], c=[1,.4,.5];
const resolved=average([bg,c,a,a]);
resolved.forEach((x,i)=>near(x,[1,.75,.475][i]));

function clipHistory(history,lo,hi) {
 const center=lo.map((v,i)=>(v+hi[i])*.5);
 const extent=lo.map((v,i)=>Math.max((hi[i]-v)*.5,1e-5));
 const offset=history.map((v,i)=>v-center[i]);
 const scale=Math.max(1,...offset.map((v,i)=>Math.abs(v)/extent[i]));
 return center.map((v,i)=>v+offset[i]/scale);
}
assert.deepEqual(clipHistory([.2,.3,.4],[0,0,0],[1,1,1]),[.2,.3,.4]);
const clipped=clipHistory([3,2,-1],[0,0,0],[1,1,1]);
clipped.forEach(v=>assert.ok(v>=0 && v<=1));
assert.ok(clipHistory([1,1,1],[.2,.2,.2],[.2,.2,.2]).every(Number.isFinite));

// Recurrence preserves a constant signal; an initial impulse decays geometrically.
for (const alpha of [.1,.25,1]) {
 let h=1;
 for(let k=1;k<=30;k++){ h=(1-alpha)*h; near(h,(1-alpha)**k); }
 let constant=.7;
 for(let k=0;k<30;k++) constant=alpha*.7+(1-alpha)*constant;
 near(constant,.7);
}

// The 2x2 binary illustration has 16 distinct weighted outcomes.
const codes=new Set();
for(let mask=0;mask<16;mask++){
 const bits=[0,1,2,3].map(i=>(mask>>i)&1);
 codes.add(10*bits[0]+5*bits[1]+2*bits[2]+bits[3]);
}
assert.equal(codes.size,16);
const colorMiB=1920*1080*4*8/(1024**2);
console.log({resolved,clipped,colorMiB,distinctBinaryCodes:codes.size});
console.log('Passed: resolve arithmetic, clipping bounds, temporal recurrence, binary encoding.');
