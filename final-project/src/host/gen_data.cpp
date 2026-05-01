#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#include "hnswlib/hnswlib.h"

#include "common/io.hpp"

struct Args {
    uint32_t n_vectors = 1000;
    uint32_t n_queries = 50;
    uint32_t dim = 16;
    uint32_t m = 8;
    uint32_t ef_construction = 50;
    uint32_t seed = 42;
    std::string out_dir = "data";
};

static std::vector<float> generate_vectors(uint32_t N, uint32_t D, std::mt19937& rng) {
    std::normal_distribution<float> normal(0.0f, 1.0f);
    std::vector<float> v(static_cast<std::size_t>(N) * D);
    for (auto& x : v)
        x = normal(rng);
    return v;
}

// Builds an HNSW index with hnswlib, then converts to custom HNSW format
static HnswGraph build_hnsw(const std::vector<float>& vectors, uint32_t N, uint32_t D, uint32_t M,
                            uint32_t ef_construction, uint32_t seed) {
    hnswlib::L2Space space(D);
    hnswlib::HierarchicalNSW<float> index(&space, N, M, ef_construction, seed);

    for (uint32_t i = 0; i < N; ++i) {
        index.addPoint(vectors.data() + static_cast<std::size_t>(i) * D, i);
    }

    HnswGraph g;
    g.N = N;
    g.D = D;
    g.M = static_cast<uint32_t>(index.maxM_);
    g.M0 = static_cast<uint32_t>(index.maxM0_);
    g.max_level = static_cast<uint32_t>(index.maxlevel_);
    g.entry_point = static_cast<uint32_t>(index.enterpoint_node_);
    g.vectors = vectors;

    g.levels.resize(N);
    for (uint32_t i = 0; i < N; ++i)
        g.levels[i] = static_cast<uint8_t>(index.element_levels_[i]);

    g.layer0_nbrs.assign(static_cast<std::size_t>(N) * g.M0, HNSW_NEIGHBOR_SENTINEL);
    for (uint32_t i = 0; i < N; ++i) {
        auto* ll = index.get_linklist0(i);
        const auto count = index.getListCount(ll);
        const auto* neighbors = ll + 1;
        const std::size_t row_offset = static_cast<std::size_t>(i) * g.M0;
        for (unsigned int j = 0; j < count; ++j)
            g.layer0_nbrs[row_offset + j] = neighbors[j];
    }

    if (g.max_level > 0) {
        g.upper_nbrs.assign(static_cast<std::size_t>(N) * g.max_level * g.M, HNSW_NEIGHBOR_SENTINEL);
        for (uint32_t i = 0; i < N; ++i) {
            const int node_top_level = index.element_levels_[i];
            for (int lvl = 1; lvl <= node_top_level; ++lvl) {
                auto* ll = index.get_linklist(i, lvl);
                const auto count = index.getListCount(ll);
                const auto* neighbors = ll + 1;
                const std::size_t row_offset = (static_cast<std::size_t>(i) * g.max_level + (lvl - 1)) * g.M;
                for (unsigned int j = 0; j < count; ++j)
                    g.upper_nbrs[row_offset + j] = neighbors[j];
            }
        }
    }

    return g;
}

static void verify_vectors_on_disk(const std::string& path, const std::vector<float>& original, uint32_t N,
                                   uint32_t D) {
    const VectorSet loaded = load_vectors(path);
    if (loaded.N != N || loaded.D != D || loaded.data != original) {
        std::cerr << "FAIL: " << path << " round-trip mismatch\n";
        std::exit(1);
    }
}

static void verify_hnsw_on_disk(const std::string& path, const HnswGraph& original) {
    const HnswGraph loaded = load_hnsw(path);
    const bool ok = loaded.N == original.N && loaded.D == original.D && loaded.M == original.M &&
                    loaded.M0 == original.M0 && loaded.max_level == original.max_level &&
                    loaded.entry_point == original.entry_point && loaded.vectors == original.vectors &&
                    loaded.levels == original.levels && loaded.layer0_nbrs == original.layer0_nbrs &&
                    loaded.upper_nbrs == original.upper_nbrs;
    if (!ok) {
        std::cerr << "FAIL: " << path << " round-trip mismatch\n";
        std::exit(1);
    }
}

static Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        const std::string flag = argv[i];
        if (i + 1 >= argc) {
            std::cerr << "missing value for " << flag << "\n";
            std::exit(1);
        }
        if (flag == "--n-vectors")
            args.n_vectors = std::stoul(argv[++i]);
        else if (flag == "--n-queries")
            args.n_queries = std::stoul(argv[++i]);
        else if (flag == "--dim")
            args.dim = std::stoul(argv[++i]);
        else if (flag == "--m")
            args.m = std::stoul(argv[++i]);
        else if (flag == "--ef-construction")
            args.ef_construction = std::stoul(argv[++i]);
        else if (flag == "--seed")
            args.seed = std::stoul(argv[++i]);
        else if (flag == "--out-dir")
            args.out_dir = argv[++i];
        else {
            std::cerr << "unknown flag: " << flag << "\n";
            std::exit(1);
        }
    }
    return args;
}

int main(int argc, char** argv) {
    const Args args = parse_args(argc, argv);
    std::filesystem::create_directories(args.out_dir);

    std::mt19937 rng(args.seed);
    const auto vectors = generate_vectors(args.n_vectors, args.dim, rng);
    const auto queries = generate_vectors(args.n_queries, args.dim, rng);

    const std::string vectors_path = args.out_dir + "/vectors.bin";
    write_vectors(vectors_path, args.n_vectors, args.dim, vectors.data());
    verify_vectors_on_disk(vectors_path, vectors, args.n_vectors, args.dim);
    std::cout << "wrote " << vectors_path << " (N=" << args.n_vectors << " D=" << args.dim << ")\n";

    const std::string queries_path = args.out_dir + "/queries.bin";
    write_vectors(queries_path, args.n_queries, args.dim, queries.data());
    verify_vectors_on_disk(queries_path, queries, args.n_queries, args.dim);
    std::cout << "wrote " << queries_path << " (N=" << args.n_queries << " D=" << args.dim << ")\n";

    const HnswGraph graph = build_hnsw(vectors, args.n_vectors, args.dim, args.m, args.ef_construction, args.seed);
    const std::string hnsw_path = args.out_dir + "/hnsw.bin";
    write_hnsw(hnsw_path, graph);
    verify_hnsw_on_disk(hnsw_path, graph);
    std::cout << "wrote " << hnsw_path << " (M=" << graph.M << " M0=" << graph.M0 << " max_level=" << graph.max_level
              << " entry_point=" << graph.entry_point << ")\n";

    return 0;
}
