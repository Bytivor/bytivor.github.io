// UE Custom expression BODY. Output: CMOT Float1.
// Inputs (all Float1): SdfValue, Light01, AAWidthPx, ViewDepthCM,
// NearCM, FarCM, FarWidthScale, MinFieldWidth.
// Pixel stage only. Sample the texture outside this Custom node.
// SdfValue / Light01 conventions must match the authored face threshold field.
float light = lerp(-0.1, 1.1, saturate(Light01));
float d = SdfValue + light - 1.0;
float gradient = fwidth(d);
float t = smoothstep(NearCM, max(FarCM, NearCM + 1.0), max(ViewDepthCM, 0.0));
float nearWidth = max(AAWidthPx, 1.0);
float widthPx = max(1.0, lerp(nearWidth,
    nearWidth * saturate(FarWidthScale), t));
float halfWidth = max(0.5 * widthPx * gradient, max(MinFieldWidth, 1e-6));
return smoothstep(-halfWidth, halfWidth, d);
