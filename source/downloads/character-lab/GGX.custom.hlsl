// UE Custom: Output CMOT Float3.
// float3: N, L, V, BaseColor. float1: Metallic, Roughness.
// Output is a BRDF; multiply by light color, NoL and visibility AFTER mixing.
float3 n = normalize(N);
float3 l = normalize(L);
float3 v = normalize(V);
float nl = saturate(dot(n, l));
float nv = saturate(dot(n, v));
float3 sumLV = l + v;
float h2 = dot(sumLV, sumLV);
if (nl <= 0.0 || nv <= 0.0 || h2 < 1e-8) return float3(0, 0, 0);
float3 h = sumLV * rsqrt(h2);
float nh = saturate(dot(n, h));
float vh = saturate(dot(v, h));
float r = clamp(Roughness, 0.08, 1.0);
float alpha = r * r;
float a2 = alpha * alpha;
// Stable form of 1 + (a2-1)*nh*nh; avoids cancellation near nh=1.
float d = (1.0 - nh * nh) + a2 * nh * nh;
float D = a2 / (3.14159265 * d * d);
float gL = 2.0 * nl / (nl + sqrt(a2 + (1.0 - a2) * nl * nl));
float gV = 2.0 * nv / (nv + sqrt(a2 + (1.0 - a2) * nv * nv));
float3 f0 = lerp(float3(0.04, 0.04, 0.04), saturate(BaseColor), saturate(Metallic));
float3 F = f0 + (1.0 - f0) * pow(1.0 - vh, 5.0);
return D * F * gL * gV / max(4.0 * nl * nv, 1e-8);
