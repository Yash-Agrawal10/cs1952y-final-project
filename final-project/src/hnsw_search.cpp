#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <queue>
#include <string>
#include <utility>
#include <vector>

#include "common/distance.hpp"
#include "common/io.hpp"

struct Args {
    std::string hnsw_path = "data/hnsw.bin";
    std::string queries_path = "data/queries.bin";
    uint32_t k = 10;
    uint32_t ef = 50;
};

static Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        const std::string flag = argv[i];
        if (i + 1 >= argc) {
            std::cerr << "missing value for " << flag << "\n";
            std::exit(1);
        }
        if (flag == "--hnsw")
            args.hnsw_path = argv[++i];
        else if (flag == "--queries")
            args.queries_path = argv[++i];
        else if (flag == "--k")
            args.k = std::stoul(argv[++i]);
        else if (flag == "--ef")
            args.ef = std::stoul(argv[++i]);
        else {
            std::cerr << "unknown flag: " << flag << "\n";
            std::exit(1);
        }
    }
    return args;
}

using DistNode = std::pair<float, uint32_t>;

static std::vector<DistNode> hnsw_topk(const HnswGraph& g, const float* query, uint32_t k, uint32_t ef,
                                       std::vector<bool>& visited) {
    std::fill(visited.begin(), visited.end(), false);

    // Phase 1: greedy descent
    uint32_t curr = g.entry_point;
    float curr_dist = l2_sq(query, g.vec(curr), g.D);
    for (uint32_t lvl = g.max_level; lvl > 0; --lvl) {
        bool improved = true;
        while (improved) {
            improved = false;
            auto [b, e] = g.nbrs(curr, lvl);
            for (auto p = b; p != e; ++p) {
                const float d = l2_sq(query, g.vec(*p), g.D);
                if (d < curr_dist) {
                    curr = *p;
                    curr_dist = d;
                    improved = true;
                }
            }
        }
    }

    // Phase 2: beam search at layer 0
    std::priority_queue<DistNode, std::vector<DistNode>, std::greater<>> candidates;
    std::priority_queue<DistNode> results;
    candidates.emplace(curr_dist, curr);
    results.emplace(curr_dist, curr);
    visited[curr] = true;

    while (!candidates.empty()) {
        const auto [c_dist, c_node] = candidates.top();
        candidates.pop();
        if (c_dist > results.top().first)
            break;

        auto [b, e] = g.nbrs(c_node, 0);
        for (auto p = b; p != e; ++p) {
            const uint32_t nbr = *p;
            if (visited[nbr])
                continue;
            visited[nbr] = true;

            const float d = l2_sq(query, g.vec(nbr), g.D);
            if (results.size() < ef || d < results.top().first) {
                candidates.emplace(d, nbr);
                results.emplace(d, nbr);
                if (results.size() > ef)
                    results.pop();
            }
        }
    }

    // Phase 3: extract top k
    std::vector<DistNode> out;
    out.reserve(results.size());
    while (!results.empty()) {
        out.push_back(results.top());
        results.pop();
    }
    std::reverse(out.begin(), out.end());
    if (out.size() > k)
        out.resize(k);
    return out;
}

int main(int argc, char** argv) {
    const Args args = parse_args(argc, argv);

    if (args.ef < args.k) {
        std::cerr << "ef (" << args.ef << ") must be >= k (" << args.k << ")\n";
        return 1;
    }

    const HnswGraph g = load_hnsw(args.hnsw_path);
    const VectorSet queries = load_vectors(args.queries_path);

    if (g.D != queries.D) {
        std::cerr << "FAIL: g.D=" << g.D << " != queries.D=" << queries.D << "\n";
        return 1;
    }

    std::cout << "hnsw search: db_N=" << g.N << " queries_N=" << queries.N << " D=" << g.D << " K=" << args.k
              << " ef=" << args.ef << " max_level=" << g.max_level << " entry_point=" << g.entry_point << "\n";

    std::vector<bool> visited(g.N);

    uint64_t checksum = 0;
    for (uint32_t q = 0; q < queries.N; ++q) {
        const auto results = hnsw_topk(g, queries.vec(q), args.k, args.ef, visited);
        for (const auto& [dist, idx] : results)
            checksum += idx;

        if (q == 0) {
            std::cout << "query[0] top-" << args.k << ":";
            for (const auto& [dist, idx] : results)
                std::cout << " " << idx << "(" << dist << ")";
            std::cout << "\n";
        }
    }

    std::cout << "checksum: " << checksum << "\n";
    return 0;
}
