// Bytivor: original educational HLSL helpers, extracted from the article.
// Not a UE plugin or a complete shader; engine bindings and entry points are omitted.
// Vectors are normalized; colors are linear; functions use the conventions in the article.
// ComposeToonKey is evaluated ONCE per pixel, not once per light.

float ToonBand(float h, float threshold, float feather, float pixelWidth)
{
    float width = max(max(feather, 0.5 * pixelWidth), 1e-4);
    return smoothstep(threshold - width, threshold + width, h);
}

float HalfLambert(float3 N, float3 L)
{
    return saturate(0.5 * dot(N, L) + 0.5);
}


float3 SampleToonRamp(Texture2D<float4> atlas,
                      SamplerState linearClamp,
                      float h, uint row,
                      uint width, uint rowCount)
{
    // Preconditions: width >= 2, rowCount >= 1; texture size matches.
    row = min(row, rowCount - 1);
    float u = (0.5 + saturate(h) * (width - 1)) / width;
    float v = (row + 0.5) / rowCount;
    return atlas.SampleLevel(linearClamp, float2(u, v), 0).rgb;
}


float3 ComposeToonKey(float3 shadowColor, float3 litColor,
                      float band, float visibility)
{
    float weight = saturate(band) * saturate(visibility);
    return lerp(shadowColor, litColor, weight);
}


float PCF3x3(Texture2D<float> shadowMap,
             SamplerComparisonState cmpLessEqual,
             float2 uv, float receiverDepth,
             float2 invShadowSize, float bias)
{
    float sum = 0.0;
    [unroll] for (int y = -1; y <= 1; ++y)
    {
        [unroll] for (int x = -1; x <= 1; ++x)
        {
            float2 offset = float2(x, y) * invShadowSize;
            sum += shadowMap.SampleCmpLevelZero(
                cmpLessEqual, uv + offset, receiverDepth - bias);
        }
    }
    return sum / 9.0;
}


float3 FaceNormalFromBasis(float3 detailTS,
                           float3 faceRightWS,
                           float3 faceUpWS,
                           float3 faceForwardWS)
{
    // Basis must be orthonormal and follow the animated head.
    float3 n = detailTS.x * faceRightWS
             + detailTS.y * faceUpWS
             + detailTS.z * faceForwardWS;
    return normalize(n);
}


float ToonSpecular(float3 N, float3 L, float3 viewDir,
                    float exponent, float threshold, float feather)
{
    float3 sum = L + viewDir;
    float len2 = dot(sum, sum);
    if (len2 < 1e-6) return 0.0;
    float3 H = sum * rsqrt(len2);
    float p = pow(saturate(dot(N, H)), max(exponent, 1.0));
    float f = max(feather, 1e-4);
    return smoothstep(threshold - f, threshold + f, p);
}


float2 EdgePair(float centerDepth, float neighborDepth,
                 float3 centerNormal, float3 neighborNormal)
{
    float dz = abs(neighborDepth - centerDepth)
             / max(centerDepth, 1e-3);
    float dn = 1.0 - clamp(dot(centerNormal, neighborNormal), -1.0, 1.0);
    return float2(dz, dn);
}
