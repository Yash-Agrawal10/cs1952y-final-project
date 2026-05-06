import argparse
import csv
import pathlib
import re
import subprocess
import sys

TIME_RE = re.compile(r"search_time_ns:\s*(\d+)")


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


def time_ns(stdout):
    m = TIME_RE.search(stdout)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--n-vectors", type=int, nargs="+", default=[1000, 5000, 10000, 50000])
    ap.add_argument("--n-queries", type=int, default=200)
    ap.add_argument("--dim", type=int, default=16)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--ef", type=int, default=50)
    ap.add_argument("--m", type=int, default=8)
    ap.add_argument("--ef-construction", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default="out/H1_run")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.project_root).resolve()
    out_dir = (root / args.out_dir).resolve()
    data_dir = out_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_build:
        for c in [
            ["make", "clean"],
            ["make", "host",
             "HOST_CXXFLAGS=-std=c++17 -O3 -Wall -Wextra -fno-tree-vectorize -fno-tree-slp-vectorize",
             "HOST_SIMD_CXXFLAGS=-std=c++17 -O3 -Wall -Wextra -march=native -ftree-vectorize"],
        ]:
            rc, so, se = run(c)
            if rc != 0:
                print(se, file=sys.stderr)
                sys.exit(rc)

    rows = []

    for nv in args.n_vectors:
        gen = [
            str(root / "binaries/host/gen_data"),
            "--n-vectors", str(nv),
            "--n-queries", str(args.n_queries),
            "--dim", str(args.dim),
            "--m", str(args.m),
            "--ef-construction", str(args.ef_construction),
            "--seed", str(args.seed),
            "--out-dir", str(data_dir),
        ]
        rc, so, se = run(gen)
        if rc != 0:
            print(se, file=sys.stderr)
            sys.exit(rc)

        runs = [
            ("flat", "scalar", [str(root / "binaries/host/flat_search"), "--vectors", str(data_dir / "vectors.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k)]),
            ("flat", "simd", [str(root / "binaries/host/flat_search_simd"), "--vectors", str(data_dir / "vectors.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k)]),
            ("hnsw", "scalar", [str(root / "binaries/host/hnsw_search"), "--hnsw", str(data_dir / "hnsw.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k), "--ef", str(args.ef)]),
            ("hnsw", "simd", [str(root / "binaries/host/hnsw_search_simd"), "--hnsw", str(data_dir / "hnsw.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k), "--ef", str(args.ef)]),
        ]

        for algo, var, cmd in runs:
            rc, so, se = run(cmd)
            rows.append({
                "n_vectors": nv,
                "n_queries": args.n_queries,
                "dim": args.dim,
                "k": args.k,
                "ef": args.ef,
                "algo": algo,
                "variant": var,
                "search_time_ns": time_ns(so) if rc == 0 else "",
                "returncode": rc,
                "command": " ".join(cmd),
                "stderr": se.strip().replace("\n", " | "),
            })

    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote CSV: {csv_path}")

    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; skipping plots")
        return

    xs = args.n_vectors

    def series(algo, variant):
        vals = []
        for nv in xs:
            v = None
            for r in rows:
                if r["n_vectors"] == nv and r["algo"] == algo and r["variant"] == variant:
                    t = r["search_time_ns"]
                    v = float(t) if t != "" else None
                    break
            vals.append(v)
        return vals

    flat_s = series("flat", "scalar")
    flat_v = series("flat", "simd")
    hnsw_s = series("hnsw", "scalar")
    hnsw_v = series("hnsw", "simd")

    plt.figure(figsize=(9, 5))
    plt.plot(xs, flat_s, "-o", label="Flat Scalar")
    plt.plot(xs, flat_v, "-o", label="Flat SIMD")
    plt.plot(xs, hnsw_s, "-o", label="HNSW Scalar")
    plt.plot(xs, hnsw_v, "-o", label="HNSW SIMD")
    plt.xlabel("n_vectors")
    plt.ylabel("search_time_ns")
    plt.title("H1 Time vs Dataset Size")
    plt.grid(True, alpha=0.3)
    plt.legend()
    p1 = out_dir / "h1_times_vs_nvectors.png"
    plt.tight_layout(); plt.savefig(p1, dpi=150); plt.close()

    def ratio(a, b):
        out = []
        for x, y in zip(a, b):
            out.append(None if (x is None or y is None or y == 0) else x / y)
        return out

    flat_r = ratio(flat_v, flat_s)
    hnsw_r = ratio(hnsw_v, hnsw_s)

    plt.figure(figsize=(9, 5))
    plt.plot(xs, flat_r, "-o", label="Flat SIMD/Scalar")
    plt.plot(xs, hnsw_r, "-o", label="HNSW SIMD/Scalar")
    plt.axhline(1.0, linestyle="--", linewidth=1)
    plt.xlabel("n_vectors")
    plt.ylabel("speedup ratio (SIMD/Scalar)")
    plt.title("H1 Speedup vs Dataset Size")
    plt.grid(True, alpha=0.3)
    plt.legend()
    p2 = out_dir / "h1_speedup_vs_nvectors.png"
    plt.tight_layout(); plt.savefig(p2, dpi=150); plt.close()

    print(f"Wrote plot: {p1}")
    print(f"Wrote plot: {p2}")


if __name__ == "__main__":
    main()
    
    
# cd /home/cs1952y-user/gem5/final-project
# python3 scripts/H1_run.py --n-vectors 1000 2000 4000 8000 16000 32000 64000 128000 256000 512000
