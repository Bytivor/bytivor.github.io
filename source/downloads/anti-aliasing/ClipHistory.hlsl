// Same color space for all inputs. lo <= hi component-wise.
// Center-directed box clipping; not a complete temporal AA implementation.
float3 ClipHistoryToBox(float3 history, float3 lo, float3 hi)
{
    float3 center = 0.5 * (lo + hi);
    float3 extent = max(0.5 * (hi - lo), 1e-5);
    float3 offset = history - center;
    float3 normalized = abs(offset) / extent;
    float scale = max(1.0, max(normalized.x,
                             max(normalized.y, normalized.z)));
    return center + offset / scale;
}
