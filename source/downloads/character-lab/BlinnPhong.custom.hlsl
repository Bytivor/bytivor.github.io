// UE Custom: Output CMOT Float3.
// float3: N, L, V, SpecularColor. float1: Exponent.
// Artistic, unnormalized lobe. It is NOT an energy-conserving BRDF.
float3 n = normalize(N);
float3 l = normalize(L);
float3 v = normalize(V);
float3 sumLV = l + v;
float h2 = dot(sumLV, sumLV);
if (dot(n, l) <= 0.0 || dot(n, v) <= 0.0 || h2 < 1e-8)
    return float3(0, 0, 0);
float nh = saturate(dot(n, sumLV * rsqrt(h2)));
return max(SpecularColor, 0.0) * pow(nh, max(Exponent, 1.0));
