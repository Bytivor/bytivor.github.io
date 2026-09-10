float d = clamp(Duty, 0.001, 0.999);
float2 w = max(abs(ddx(P)) + abs(ddy(P)), 1e-5);
float2 lo = P - 0.5 * w;
float2 hi = P + 0.5 * w;
// 周期脉冲的原函数：floor(x)*d + min(frac(x), d)
float2 Ilo = floor(lo) * d + min(frac(lo), d);
float2 Ihi = floor(hi) * d + min(frac(hi), d);
float2 a = saturate((Ihi - Ilo) / w);
float coverage = 1.0 - (1.0-a.x) * (1.0-a.y);
float meanCoverage = 1.0 - (1.0-d) * (1.0-d);
float footprint = max(w.x, w.y);
float fade = smoothstep(0.75, 2.0, footprint);
return float2(lerp(coverage, meanCoverage, fade), footprint);
