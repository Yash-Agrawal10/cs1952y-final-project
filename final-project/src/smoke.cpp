// smoke.cpp — minimal workload to verify run.py end-to-end.
//
// Touches all three layers of the simulated memory hierarchy:
//   * a small array (fits in L1)        -> proves CPU + L1 work
//   * a medium array (overflows L1)     -> proves L2 path works
//   * a checksum print                  -> proves stdout is captured

#include <cstdio>
#include <cstdint>

constexpr int SMALL = 1024;       // 4kB, fits in L1
constexpr int LARGE = 64 * 1024;  // 256kB, blows L1, lives in L2

static int small_arr[SMALL];
static int large_arr[LARGE];

int main() {
    // Init both arrays so memory really gets touched.
    for (int i = 0; i < SMALL; i++) small_arr[i] = i;
    for (int i = 0; i < LARGE; i++) large_arr[i] = i * 3;

    // Hot loop on the small array (L1-friendly).
    int64_t s = 0;
    for (int rep = 0; rep < 100; rep++)
        for (int i = 0; i < SMALL; i++)
            s += small_arr[i];

    // Linear sweep over the large array (L1 misses, L2 hits).
    for (int i = 0; i < LARGE; i++)
        s += large_arr[i];

    printf("smoke checksum=%lld\n", (long long)s);
    return 0;
}
