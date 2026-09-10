// UE Custom: Output CMOT Float1. All inputs are float1.
// Inputs: NoL, RampOffset, Center, Sharpness, AO, AOStrength, Visibility
// NoL is the SIGNED dot product in [-1,1], not Half Lambert.
float x = NoL + RampOffset;
float exponent = clamp(-max(Sharpness, 0.0) * (x - Center), -80.0, 80.0);
float lit = 1.0 / (1.0 + exp2(exponent));
float ao = lerp(1.0, saturate(AO), saturate(AOStrength));
return lit * ao * saturate(Visibility);
