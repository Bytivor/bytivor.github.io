// CPU algebra checks only. GPU derivatives and UE compilation are not exercised.
const assert=require('node:assert/strict');
const sat=x=>Math.min(1,Math.max(0,x));
function smooth(a,b,x){const t=sat((x-a)/(b-a));return t*t*(3-2*t);}
function evaluate(d,g,{width=1.5,depth=0,near=100,far=500,scale=1,minWidth=1e-5}={}) {
 const t=smooth(near,Math.max(far,near+1),Math.max(depth,0));
 const n=Math.max(width,1),px=Math.max(1,n+(n*sat(scale)-n)*t);
 const w=Math.max(.5*px*g,Math.max(minWidth,1e-6));
 return {lit:smooth(-w,w,d),w,px};
}
// Preserve the early failure as a regression target: zero width from input >= 200.
assert.equal(1-Math.min(1,(200/1000+.8)**2),0);
// The replacement remains defined with a flat field, invalid range and large depth.
for(const depth of [-10,0,199,200,500,1e6])for(const gradient of [0,1e-8,.01,1]){
 const p=evaluate(0,gradient,{depth,near:500,far:100,scale:0,minWidth:0});
 assert(Number.isFinite(p.lit)&&p.w>0&&p.px>=1);assert.equal(p.lit,.5);
}
// A linear field observed at different scales has identical pixel-relative coverage.
for(const x of [-2,-.6,-.2,0,.2,.6,2]){
 const a=evaluate(x*.01,.01).lit,b=evaluate(x*.1,.1).lit;
 assert(Math.abs(a-b)<1e-12);
}
let prev=-1;
for(let i=0;i<=200;i++){const v=evaluate((i-100)/100,.1).lit;assert(v>=prev&&v>=0&&v<=1);prev=v;}
// Default distance settings preserve the baseline. Optional shrink stays >= 1 pixel.
for(const depth of [0,100,200,500,1e6]) {
 assert.equal(evaluate(.02,.1,{depth}).px,1.5);
 assert(evaluate(.02,.1,{depth,scale:.01}).px>=1);
}
console.log('PASS: no zero-width degeneracy; monotonic coverage; pixel-scale invariance; safe distance range. UE compilation not performed.');
