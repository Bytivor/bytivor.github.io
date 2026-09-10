// Independent CPU model of the five teaching kernels; NOT a UE shader compiler.
const clamp = (x,a,b) => Math.max(a,Math.min(b,x));
const dot = (a,b) => a.reduce((v,x,i)=>v+x*b[i],0);
const norm = a => {const l=Math.hypot(...a); if(!l) throw Error('zero direction'); return a.map(x=>x/l);};
const smooth = (a,b,x) => {const t=clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};
function diffuse(n,offset=0,center=0,k=12,ao=1,strength=1,visibility=1){
  const e=clamp(-Math.max(k,0)*(n+offset-center),-80,80);
  return 1/(1+2**e)*(1+(clamp(ao,0,1)-1)*clamp(strength,0,1))*clamp(visibility,0,1);
}
function distribution(nh,r){
  const a2=clamp(r,.08,1)**4;
  const d=1-nh*nh+a2*nh*nh;
  return a2/(Math.PI*d*d);
}
function ggx(N,L,V,base=[.5,.5,.5],metal=0,rough=.4){
  const n=norm(N),l=norm(L),v=norm(V);
  const nl=clamp(dot(n,l),0,1),nv=clamp(dot(n,v),0,1);
  const h0=l.map((x,i)=>x+v[i]),h2=dot(h0,h0);
  if(nl<=0||nv<=0||h2<1e-8)return [0,0,0];
  const h=norm(h0),nh=clamp(dot(n,h),0,1),vh=clamp(dot(v,h),0,1),a2=clamp(rough,.08,1)**4;
  const g=c=>2*c/(c+Math.sqrt(a2+(1-a2)*c*c));
  const scale=distribution(nh,rough)*g(nl)*g(nv)/Math.max(4*nl*nv,1e-8);
  return base.map(b=>{const f0=.04+(clamp(b,0,1)-.04)*clamp(metal,0,1);return (f0+(1-f0)*(1-vh)**5)*scale;});
}
function blinn(N,L,V,p=32){
  const n=norm(N),l=norm(L),v=norm(V),sum=l.map((x,i)=>x+v[i]);
  if(dot(n,l)<=0||dot(n,v)<=0||dot(sum,sum)<1e-8)return 0;
  return clamp(dot(n,norm(sum)),0,1)**Math.max(p,1);
}
function rim(center,neighbors,threshold=.02,softness=.005,mask=1){
  const gap=Math.max(Math.max(...neighbors)-center,0)/Math.max(center,1);
  const t=Math.max(threshold,1e-5),s=clamp(softness,1e-6,t*.99);
  return smooth(t-s,t+s,gap)*clamp(mask,0,1);
}
function outline(N,R,U,F,width,alpha,blue,bias){
  const n=norm(N),nx=dot(n,R),ny=dot(n,U),nz=bias*(1-clamp(blue,0,1));
  return R.map((x,i)=>(x*nx+U[i]*ny+F[i]*nz)*Math.max(width,0)*clamp(alpha,0,1));
}
module.exports={diffuse,distribution,ggx,blinn,rim,outline};
