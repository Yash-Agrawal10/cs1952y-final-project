import argparse
import csv
import statistics
import pathlib
import re
import shutil
import subprocess
import sys

TIME_RE = re.compile(r"search_time_ns:\s*(\d+)")


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


def time_ns(stdout):
    m = TIME_RE.search(stdout)
    return int(m.group(1)) if m else None


def compiler_tag(compiler):
    name = pathlib.Path(compiler).name
    if "clang" in name:
        return "clang"
    if "g++" in name or "gcc" in name:
        return "gcc"
    return name.replace("+", "x")


def report_flags(tag):
    if tag == "gcc":
        scalar = "-std=c++17 -O3 -Wall -Wextra -fno-tree-vectorize -fno-tree-slp-vectorize -fopt-info-vec-missed"
        simd = "-std=c++17 -O3 -Wall -Wextra -march=native -ftree-vectorize -fopt-info-vec-optimized -fopt-info-vec-missed"
    elif tag == "clang":
        scalar = "-std=c++17 -O3 -Wall -Wextra -fno-vectorize -fno-slp-vectorize -Rpass-missed=loop-vectorize"
        simd = "-std=c++17 -O3 -Wall -Wextra -mcpu=native -Rpass=loop-vectorize -Rpass-missed=loop-vectorize"
    else:
        scalar = "-std=c++17 -O3 -Wall -Wextra"
        simd = "-std=c++17 -O3 -Wall -Wextra -march=native -ftree-vectorize"
    return scalar, simd


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def summarize_report(tag, text):
    lines = [line for line in text.splitlines() if "distance.hpp" in line or "flat_search.cpp" in line or "hnsw_search.cpp" in line]
    if tag == "gcc":
        vectorized = sum("optimized: loop vectorized" in line for line in lines)
        missed = sum("missed:" in line for line in lines)
    elif tag == "clang":
        vectorized = sum("remark: vectorized loop" in line for line in lines)
        missed = sum("remark: loop not vectorized" in line for line in lines)
    else:
        vectorized = 0
        missed = 0
    return vectorized, missed, lines


def build_compiler(root, compiler, out_dir):
    tag = compiler_tag(compiler)
    scalar_flags, simd_flags = report_flags(tag)

    rows = []
    logs = {}
    for cmd in [
        ["make", "clean"],
        ["make", "host", f"HOST_CXX={compiler}", f"HOST_CXXFLAGS={scalar_flags}", f"HOST_SIMD_CXXFLAGS={simd_flags}"],
    ]:
        rc, so, se = run(cmd, cwd=root)
        logs[" ".join(cmd)] = (rc, so, se)
        if rc != 0:
            write_text(out_dir / "reports" / f"{tag}_build.log", so + "\n" + se)
            print(se, file=sys.stderr)
            sys.exit(rc)

    combined_log = []
    for cmd, (rc, so, se) in logs.items():
        combined_log.append(f"$ {cmd}\n[rc={rc}]\n")
        if so:
            combined_log.append(so)
        if se:
            combined_log.append(se)
        combined_log.append("\n")
    combined_text = "".join(combined_log)
    write_text(out_dir / "reports" / f"{tag}_build.log", combined_text)

    vectorized, missed, interesting = summarize_report(tag, combined_text)
    write_text(out_dir / "reports" / f"{tag}_vectorization_excerpt.txt", "\n".join(interesting) + ("\n" if interesting else ""))
    rows.append({
        "compiler": tag,
        "vectorized_mentions": vectorized,
        "missed_mentions": missed,
        "report_path": str((out_dir / "reports" / f"{tag}_build.log").resolve()),
        "excerpt_path": str((out_dir / "reports" / f"{tag}_vectorization_excerpt.txt").resolve()),
    })

    bin_dir = out_dir / "bin" / tag
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in ["gen_data", "flat_search", "flat_search_simd", "hnsw_search", "hnsw_search_simd"]:
        shutil.copy2(root / "binaries" / "host" / name, bin_dir / name)
    return tag, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--compilers", nargs="+", default=["g++", "clang++"])
    ap.add_argument("--n-vectors", type=int, nargs="+", default=[1000, 5000, 10000, 50000])
    ap.add_argument("--n-queries", type=int, default=200)
    ap.add_argument("--dim", type=int, default=16)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--ef", type=int, default=50)
    ap.add_argument("--m", type=int, default=8)
    ap.add_argument("--ef-construction", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default="out/H1_compiler_check")
    ap.add_argument("--num-runs", type=int, default=5)
    ap.add_argument("--plot-compilers", nargs="+", default=["gcc", "clang"])
    args = ap.parse_args()

    root = pathlib.Path(args.project_root).resolve()
    out_dir = (root / args.out_dir).resolve()
    data_dir = out_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    compiler_rows = []
    result_rows = []
    built = []
    for compiler in args.compilers:
        tag, rows = build_compiler(root, compiler, out_dir)
        compiler_rows.extend(rows)
        built.append(tag)

    for nv in args.n_vectors:
        gen = [
            str(out_dir / "bin" / built[0] / "gen_data"),
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

        for tag in built:
            runs = [
                ("flat", "scalar", [str(out_dir / "bin" / tag / "flat_search"), "--vectors", str(data_dir / "vectors.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k)]),
                ("flat", "simd", [str(out_dir / "bin" / tag / "flat_search_simd"), "--vectors", str(data_dir / "vectors.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k)]),
                ("hnsw", "scalar", [str(out_dir / "bin" / tag / "hnsw_search"), "--hnsw", str(data_dir / "hnsw.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k), "--ef", str(args.ef)]),
                ("hnsw", "simd", [str(out_dir / "bin" / tag / "hnsw_search_simd"), "--hnsw", str(data_dir / "hnsw.bin"), "--queries", str(data_dir / "queries.bin"), "--k", str(args.k), "--ef", str(args.ef)]),
            ]
            for algo, var, cmd in runs:
                times = []
                rc = 0
                stderr_parts = []
                for _ in range(args.num_runs):
                    rc, so, se = run(cmd)
                    if rc != 0:
                        stderr_parts.append(se.strip())
                        break
                    t = time_ns(so)
                    if t is None:
                        rc = 1
                        stderr_parts.append("missing search_time_ns in stdout")
                        break
                    times.append(t)
                    if se.strip():
                        stderr_parts.append(se.strip())

                median_ns = int(statistics.median(times)) if times else ""
                min_ns = min(times) if times else ""
                max_ns = max(times) if times else ""
                result_rows.append({
                    "compiler": tag,
                    "n_vectors": nv,
                    "n_queries": args.n_queries,
                    "dim": args.dim,
                    "k": args.k,
                    "ef": args.ef,
                    "algo": algo,
                    "variant": var,
                    "num_runs": args.num_runs,
                    "search_time_ns": median_ns if rc == 0 else "",
                    "median_search_time_ns": median_ns if rc == 0 else "",
                    "min_search_time_ns": min_ns if rc == 0 else "",
                    "max_search_time_ns": max_ns if rc == 0 else "",
                    "returncode": rc,
                    "command": " ".join(cmd),
                    "stderr": " | ".join(s for s in stderr_parts if s).replace("\n", " | "),
                })

    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(result_rows[0].keys()))
        w.writeheader()
        w.writerows(result_rows)

    compiler_csv = out_dir / "compiler_reports.csv"
    with compiler_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(compiler_rows[0].keys()))
        w.writeheader()
        w.writerows(compiler_rows)

    summary_md = out_dir / "summary.md"
    with summary_md.open("w") as f:
        f.write("# H1 compiler sensitivity summary\n\n")
        f.write("| compiler | vectorized mentions | missed mentions |\n")
        f.write("|---|---:|---:|\n")
        for row in compiler_rows:
            f.write(f"| {row['compiler']} | {row['vectorized_mentions']} | {row['missed_mentions']} |\n")
        f.write("\n")
        f.write("These counts come from compiler vectorization diagnostics, not runtime hardware counters.\n")

    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote compiler report summary: {compiler_csv}")
    print(f"Wrote markdown summary: {summary_md}")

    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; skipping plots")
        return

    xs = args.n_vectors
    x_pos = list(range(len(xs)))

    def series(comp, algo, variant):
        vals = []
        for nv in xs:
            v = None
            for row in result_rows:
                if row["compiler"] == comp and row["algo"] == algo and row["variant"] == variant and row["n_vectors"] == nv:
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

    plt.figure(figsize=(9, 5))
    for comp in built:
        if comp not in args.plot_compilers:
            continue
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
    plot_path = out_dir / "compiler_speedup_vs_nvectors.png"
    plt.tight_layout()
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Wrote plot: {plot_path}")


if __name__ == "__main__":
    main()

# python3 scripts/H1_compiler_check.py --project-root . --num-runs 40 --n-vectors 1000 2000 4000 8000 16000 32000 128000
