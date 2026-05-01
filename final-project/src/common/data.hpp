#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

#include "common/blob_format.hpp"

struct VectorSet {
    uint32_t N;
    uint32_t D;
    std::vector<float> data;

    // Pointer to the first float of vector i
    const float* vec(std::size_t i) const { return data.data() + i * D; }
};

struct HnswGraph {
    uint32_t N;
    uint32_t D;
    uint32_t M;
    uint32_t M0;
    uint32_t max_level;
    uint32_t entry_point;

    std::vector<float> vectors;        // size N * D
    std::vector<uint8_t> levels;       // size N
    std::vector<uint32_t> layer0_nbrs; // size N * M0, sentinel-padded
    std::vector<uint32_t> upper_nbrs;  // size N * max_level * M, sentinel-padded

    const float* vec(uint32_t i) const { return vectors.data() + static_cast<std::size_t>(i) * D; }

    // Returns [begin, end) over the valid neighbor IDs of `node` at `level`
    std::pair<const uint32_t*, const uint32_t*> nbrs(uint32_t node, uint32_t level) const {
        const bool is_layer0 = (level == 0);
        const uint32_t cap = is_layer0 ? M0 : M;
        const std::size_t offset = is_layer0 ? static_cast<std::size_t>(node) * M0
                                             : (static_cast<std::size_t>(node) * max_level + (level - 1)) * M;
        const uint32_t* begin = (is_layer0 ? layer0_nbrs : upper_nbrs).data() + offset;
        const uint32_t* end = begin;
        while (end != begin + cap && *end != HNSW_NEIGHBOR_SENTINEL)
            ++end;
        return { begin, end };
    }
};
