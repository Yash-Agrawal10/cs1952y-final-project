#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <queue>
#include <string>
#include <utility>
#include <vector>

#include "common/distance.hpp"
#include "common/io.hpp"
#include "common/m5_roi.hpp"

struct Args {
    std::string vectors_path = "data/vectors.bin";
    std::string queries_path = "data/queries.bin";
    uint32_t k = 10;
};

static Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        const std::string flag = argv[i];
        if (i + 1 >= argc) {
            std::cerr << "missing value for " << flag << "\n";
            std::exit(1);
        }
        if (flag == "--vectors")
            args.vectors_path = argv[++i];
        else if (flag == "--queries")
            args.queries_path = argv[++i];
        else if (flag == "--k")
            args.k = std::stoul(argv[++i]);
        else {
            std::cerr << "unknown flag: " << flag << "\n";
            std::exit(1);
        }
    }
    return args;
}

static std::vector<std::pair<float, uint32_t>> flat_topk(const VectorSet& db, const float* query, uint32_t k) {
    std::priority_queue<std::pair<float, uint32_t>> heap;

    for (uint32_t i = 0; i < db.N; ++i) {
        const float d = l2_sq(query, db.vec(i), db.D);
        if (heap.size() < k) {
            heap.emplace(d, i);
        } else if (d < heap.top().first) {
            heap.pop();
            heap.emplace(d, i);
        }
    }

    std::vector<std::pair<float, uint32_t>> result;
    result.reserve(heap.size());
    while (!heap.empty()) {
        result.push_back(heap.top());
        heap.pop();
    }
    std::reverse(result.begin(), result.end());
    return result;
}

int main(int argc, char** argv) {
    const Args args = parse_args(argc, argv);

    const VectorSet db = load_vectors(args.vectors_path);
    const VectorSet queries = load_vectors(args.queries_path);

    if (db.D != queries.D) {
        std::cerr << "FAIL: db.D=" << db.D << " != queries.D=" << queries.D << "\n";
        return 1;
    }

    std::cout << "flat search: db_N=" << db.N << " queries_N=" << queries.N << " D=" << db.D << " K=" << args.k << "\n";

    uint64_t checksum = 0;
    std::vector<std::pair<float, uint32_t>> first_query_results;

    const auto t0 = std::chrono::steady_clock::now();
    M5_ROI_BEGIN();
    for (uint32_t q = 0; q < queries.N; ++q) {
        const auto results = flat_topk(db, queries.vec(q), args.k);
        for (const auto& [dist, idx] : results)
            checksum += idx;
        if (q == 0)
            first_query_results = results;
    }
    M5_ROI_END();
    const auto t1 = std::chrono::steady_clock::now();

    std::cout << "query[0] top-" << args.k << ":";
    for (const auto& [dist, idx] : first_query_results)
        std::cout << " " << idx << "(" << dist << ")";
    std::cout << "\n";
    std::cout << "checksum: " << checksum << "\n";

    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count();
    std::cout << "search_time_ns: " << ns << "\n";

    M5_EXIT();
    return 0;
}
