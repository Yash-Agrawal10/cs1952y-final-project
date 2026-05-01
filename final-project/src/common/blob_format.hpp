#pragma once

#include <cstdint>

// Marks an empty slot in a fixed-size neighbor list
constexpr uint32_t HNSW_NEIGHBOR_SENTINEL = 0xFFFFFFFFu;

struct VectorBlobHeader {
    uint32_t N;
    uint32_t D;
};

struct HnswBlobHeader {
    uint32_t N;
    uint32_t D;
    uint32_t M;
    uint32_t M0;
    uint32_t max_level;
    uint32_t entry_point;
};
