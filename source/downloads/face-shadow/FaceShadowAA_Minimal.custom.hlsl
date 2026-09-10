// UE Custom expression BODY. Output: CMOT Float1.
// Inputs (Float1): SdfValue, Light01, AAWidthPx.
// No distance compensation. Start with this baseline.
float light = lerp(-0.1, 1.1, saturate(Light01));
float d = SdfValue + light - 1.0;
float w = max(0.5 * max(AAWidthPx, 1.0) * fwidth(d), 1e-5);
return smoothstep(-w, w, d);
