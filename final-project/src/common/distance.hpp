#pragma once

#include <cstdint>

// Squared Euclidean distance between two D-dimensional float vectors
inline float l2_sq(const float* a, const float* b, uint32_t D) {
    float sum = 0.0f;
    for (uint32_t i = 0; i < D; ++i) {
        const float diff = a[i] - b[i];
        sum += diff * diff;
    }
    return sum;
}
