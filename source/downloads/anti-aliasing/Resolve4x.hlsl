// Standalone graphics-API pixel shader example. Bind an actual 4-sample texture.
// Not a UE Material Custom body. No UE integration or GPU compilation validation.
Texture2DMS<float4, 4> SourceMS : register(t0);
float4 ResolvePS(float4 position : SV_Position) : SV_Target0
{
    int2 pixel = int2(position.xy);
    float4 sum = 0.0;
    [unroll]
    for (int sampleIndex = 0; sampleIndex < 4; ++sampleIndex)
        sum += SourceMS.Load(pixel, sampleIndex);
    return sum * 0.25;
}
