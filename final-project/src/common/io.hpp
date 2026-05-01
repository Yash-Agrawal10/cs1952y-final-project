#pragma once

#include <cstddef>
#include <cstdint>
#include <fstream>
#include <ios>
#include <string>

#include "common/blob_format.hpp"
#include "common/data.hpp"

inline void write_vectors(const std::string& path, uint32_t N, uint32_t D, const float* data) {
    std::ofstream f(path, std::ios::binary);
    f.exceptions(std::ios::failbit | std::ios::badbit);

    VectorBlobHeader header{ N, D };
    f.write(reinterpret_cast<const char*>(&header), sizeof(header));
    f.write(reinterpret_cast<const char*>(data), sizeof(float) * N * D);
}

inline VectorSet load_vectors(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    f.exceptions(std::ios::failbit | std::ios::badbit);

    VectorBlobHeader header;
    f.read(reinterpret_cast<char*>(&header), sizeof(header));

    VectorSet v{ header.N, header.D, std::vector<float>(static_cast<std::size_t>(header.N) * header.D) };
    f.read(reinterpret_cast<char*>(v.data.data()), sizeof(float) * v.data.size());
    return v;
}

inline void write_hnsw(const std::string& path, const HnswGraph& g) {
    std::ofstream f(path, std::ios::binary);
    f.exceptions(std::ios::failbit | std::ios::badbit);

    HnswBlobHeader header{ g.N, g.D, g.M, g.M0, g.max_level, g.entry_point };
    f.write(reinterpret_cast<const char*>(&header), sizeof(header));
    f.write(reinterpret_cast<const char*>(g.vectors.data()), sizeof(float) * g.vectors.size());
    f.write(reinterpret_cast<const char*>(g.levels.data()), sizeof(uint8_t) * g.levels.size());
    f.write(reinterpret_cast<const char*>(g.layer0_nbrs.data()), sizeof(uint32_t) * g.layer0_nbrs.size());
    if (g.max_level > 0) {
        f.write(reinterpret_cast<const char*>(g.upper_nbrs.data()), sizeof(uint32_t) * g.upper_nbrs.size());
    }
}

inline HnswGraph load_hnsw(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    f.exceptions(std::ios::failbit | std::ios::badbit);

    HnswBlobHeader header;
    f.read(reinterpret_cast<char*>(&header), sizeof(header));

    HnswGraph g;
    g.N = header.N;
    g.D = header.D;
    g.M = header.M;
    g.M0 = header.M0;
    g.max_level = header.max_level;
    g.entry_point = header.entry_point;

    g.vectors.resize(static_cast<std::size_t>(g.N) * g.D);
    g.levels.resize(g.N);
    g.layer0_nbrs.resize(static_cast<std::size_t>(g.N) * g.M0);
    g.upper_nbrs.resize(g.max_level == 0 ? 0 : static_cast<std::size_t>(g.N) * g.max_level * g.M);

    f.read(reinterpret_cast<char*>(g.vectors.data()), sizeof(float) * g.vectors.size());
    f.read(reinterpret_cast<char*>(g.levels.data()), sizeof(uint8_t) * g.levels.size());
    f.read(reinterpret_cast<char*>(g.layer0_nbrs.data()), sizeof(uint32_t) * g.layer0_nbrs.size());
    if (g.max_level > 0) {
        f.read(reinterpret_cast<char*>(g.upper_nbrs.data()), sizeof(uint32_t) * g.upper_nbrs.size());
    }

    return g;
}
