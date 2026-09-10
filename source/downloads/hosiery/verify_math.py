"""CPU reference checks; not a UE/HLSL compilation test."""
import numpy as np
rng=np.random.default_rng(1024)
def trans(c,tau,mu): return 1-np.clip(c,0,1)+np.clip(c,0,1)*np.exp(-np.minimum(np.maximum(tau,0)/np.clip(mu,.15,1),80))
assert np.allclose(trans(0,2,.5),1)
assert np.allclose(trans(.8,0,.5),1)
assert np.allclose(trans(1,1000,.15),0,atol=1e-20)
mu=np.linspace(.15,1,1000)
assert np.all(np.diff(trans(.8,.4,mu))>=0)
assert np.all(np.diff(trans(.8,np.linspace(0,10,1000),.8))<=0)
c=rng.uniform(-.1,1.1,(10000,1));tau=rng.uniform(-.1,10,(10000,3));T=trans(c,tau,rng.uniform(.001,1,(10000,1)))
skin=rng.random((10000,3));yarn=rng.random((10000,3));color=skin*T+yarn*(1-T)
assert np.isfinite(color).all() and (color>=0).all() and (color<=1).all()
assert (color>=np.minimum(skin,yarn)-1e-12).all() and (color<=np.maximum(skin,yarn)+1e-12).all()
def tangent(D,N):
 N=N/np.linalg.norm(N);T=D-N*np.dot(D,N)
 if np.dot(T,T)<=1e-8: T=np.cross([0,0,1] if abs(N[2])<.9 else [0,1,0],N)
 return T/max(np.linalg.norm(T),1e-6)
for N in [[0,0,1],[0,1,0],[-1,0,0],[.2,.3,.7]]:
 for D in [[0,0,0],N,[.5,.7,.1]]:
  t=tangent(np.array(D),np.array(N));assert abs(np.dot(t,N))<1e-10;assert abs(np.linalg.norm(t)-1)<1e-10
# Check periodic interval integral against independent dense point quadrature, including negative phases.
def integral(x,d): return np.floor(x)*d+np.minimum(x-np.floor(x),d)
for p in [-3.18,-.001,.02,.5,1.13]:
 for width in [.1,.8,1,2.7,10]:
  d=.16;exact=(integral(p+width/2,d)-integral(p-width/2,d))/width
  samples=p-width/2+(np.arange(200000)+.5)*width/200000
  numerical=np.mean(np.mod(samples,1)<d)
  assert abs(exact-numerical)<5e-5,(p,width,exact,numerical)
  assert -.00001<=exact<=1.00001
for p in [-10.8,-.3,.33,20.1]:
 assert np.isclose(integral(p+1,.16)-integral(p,.16),.16)
assert np.isclose(1-(1-.16)**2,.2944)
print('PASS: transmittance endpoints, monotonicity, 10000 bounded mixtures, tangent degeneracy, 25 numerical coverage integrations and periodic mean.')
