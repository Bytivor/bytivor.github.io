// 输入：DirectionWS、NormalWS；输出：单位世界空间切线。
float3 N = NormalWS / max(length(NormalWS), 1e-6);
float3 T = DirectionWS - N * dot(DirectionWS, N);
float3 axis = abs(N.z) < 0.9 ? float3(0,0,1) : float3(0,1,0);
float3 fallback = cross(axis, N);
T = dot(T,T) > 1e-8 ? T : fallback;
return T / max(length(T), 1e-6);
