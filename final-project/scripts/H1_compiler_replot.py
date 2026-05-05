import argparse
import csv
import pathlib
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="out/H1_compiler_check/results.csv")
    ap.add_argument("--out", default="out/H1_compiler_check/compiler_speedup_vs_nvectors.png")
    ap.add_argument("--plot-compilers", nargs="+", default=["gcc", "clang"])
    args = ap.parse_args()

    csv_path = pathlib.Path(args.csv).resolve()
    out_path = pathlib.Path(args.out).resolve()

    if not csv_path.exists():
        print(f"missing CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    rows = list(csv.DictReader(csv_path.open()))
    if not rows:
        print(f"empty CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; cannot replot", file=sys.stderr)
        sys.exit(1)

    xs = sorted({int(r["n_vectors"]) for r in rows})
    x_pos = list(range(len(xs)))

    def series(comp, algo, variant):
        vals = []
        for nv in xs:
            v = None
            for row in rows:
                if row["compiler"] == comp and row["algo"] == algo and row["variant"] == variant and int(row["n_vectors"]) == nv:
                    t = row["search_time_ns"]
                    v = float(t) if t != "" else None
                    break
            vals.append(v)
        return vals

    def ratio(simd, scalar):
        vals = []
        for x, y in zip(simd, scalar):
            vals.append(None if x is None or y is None or y == 0 else x / y)
        return vals

    compilers = [c for c in args.plot_compilers if any(r["compiler"] == c for r in rows)]

    plt.figure(figsize=(9, 5))
    for comp in compilers:
        flat_s = series(comp, "flat", "scalar")
        flat_v = series(comp, "flat", "simd")
        hnsw_s = series(comp, "hnsw", "scalar")
        hnsw_v = series(comp, "hnsw", "simd")
        plt.plot(x_pos, ratio(flat_v, flat_s), "-o", label=f"{comp.upper()} Flat SIMD/Scalar")
        plt.plot(x_pos, ratio(hnsw_v, hnsw_s), "--o", label=f"{comp.upper()} HNSW SIMD/Scalar")

    plt.axhline(1.0, linestyle="--", linewidth=1, color="black")
    plt.xlabel("n_vectors")
    plt.xticks(x_pos, [str(x) for x in xs])
    plt.ylabel("speedup ratio (SIMD/Scalar)")
    plt.title("H1 Compiler Sensitivity of SIMD Speedup")
    plt.grid(True, alpha=0.3)
    plt.legend()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Wrote plot: {out_path}")


if __name__ == "__main__":
    main()
