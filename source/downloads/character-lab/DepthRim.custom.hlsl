// UE Post Process Custom: Output CMOT Float1. All inputs are float1.
// CenterDepth, LeftDepth, RightDepth, UpDepth, DownDepth: linear view depths (cm).
// Threshold, Softness: relative, unitless. VisibleCharacterMask is prepared outside.
float delta = max(max(LeftDepth, RightDepth), max(UpDepth, DownDepth)) - CenterDepth;
float relativeGap = max(delta, 0.0) / max(CenterDepth, 1.0);
float t = max(Threshold, 1e-5);
float s = clamp(Softness, 1e-6, t * 0.99);
float edge = smoothstep(t - s, t + s, relativeGap);
return edge * saturate(VisibleCharacterMask);
