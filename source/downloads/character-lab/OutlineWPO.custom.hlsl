// UE Custom: Output CMOT Float3, connect ONLY to World Position Offset.
// float3: VertexNormalWS, CameraRightWS, CameraUpWS, CameraForwardWS.
// float1: WidthCM, VertexAlpha, VertexBlue, DepthBias.
// Camera axes must be an orthonormal camera frame, Forward points into the scene.
float3 n = normalize(VertexNormalWS);
float nx = dot(n, CameraRightWS);
float ny = dot(n, CameraUpWS);
float nz = DepthBias * (1.0 - saturate(VertexBlue));
float3 direction = CameraRightWS * nx + CameraUpWS * ny + CameraForwardWS * nz;
return direction * max(WidthCM, 0.0) * saturate(VertexAlpha);
