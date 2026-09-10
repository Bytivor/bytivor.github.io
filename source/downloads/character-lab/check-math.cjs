const assert=require('node:assert/strict');
const m=require('./math-reference.cjs');
let last=-1;
for(let i=0;i<=200;i++){
  const n=-1+i/100,w=m.diffuse(n);
  assert(w>=last&&w>=0&&w<=1);last=w;
  assert(m.diffuse(n,.2)>=w);
}
assert.equal(m.diffuse(0),.5);
assert.equal(m.diffuse(.5,0,0,12,1,1,0),0);
const N=[0,0,1],L=[.5,0,1],V=[-.2,0,1];
for(const rough of [.08,.25,.5,1]){
  const a=m.ggx(N,L,V,[.2,.3,.4],.7,rough),b=m.ggx(N,V,L,[.2,.3,.4],.7,rough);
  a.forEach((x,i)=>{assert(Number.isFinite(x)&&x>=0);assert(Math.abs(x-b[i])<1e-10);});
}
assert(m.ggx(N,N,N,[.4,.4,.4],1,.3)[0]>0); // metallic must NOT kill specular
assert.deepEqual(m.ggx(N,N,[0,0,-1]),[0,0,0]);
assert.equal(m.blinn(N,N,[0,0,-1]),0);
assert(m.blinn(N,L,V,16)>=m.blinn(N,L,V,96));
assert.equal(m.rim(300,[300,300,300,300]),0);
assert.equal(m.rim(300,[1000,300,300,300]),1);
assert.equal(m.rim(300,[1000,1000,1000,1000]),1); // no corner double intensity
assert.equal(m.rim(300,[1000,300,300,300],.02,.005,0),0); // occluded mask
assert.equal(m.rim(300,[100,100,100,100]),0); // closer neighbor isn't outer rim
assert.equal(m.rim(300,[306,300,300,300]),m.rim(600,[612,600,600,600]));
const args=[[1,0,0],[1,0,0],[0,1,0],[0,0,1]];
assert.deepEqual(m.outline(...args,.15,0,0,.2),[0,0,0]);
assert.deepEqual(m.outline(...args,.15,1,1,.2),[.15,0,0]);
assert.equal(m.outline(...args,.15,1,0,.2)[2],.03);
console.log('PASS: monotonic diffuse; reciprocal finite GGX; degenerate highlights; rim depth/occlusion/corners; outline vertex controls. UE compilation not performed.');
