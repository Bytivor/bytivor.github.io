float3 N = MacroNormalWS / max(length(MacroNormalWS), 1e-6);
float3 V = ViewWS / max(length(ViewWS), 1e-6);
float mu = max(abs(dot(N, V)), clamp(MuFloor, 0.02, 1.0));
float3 opticalDepth = min(max(TauRGB, 0.0) / mu, 80.0);
float3 T = 1.0 - saturate(Coverage)
         + saturate(Coverage) * exp(-opticalDepth);
return lerp(YarnColor, SkinColor, T);
