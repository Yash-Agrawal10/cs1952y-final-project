"""
H4 Analysis: Quantifying SIMD developer burden in hnswlib and FAISS.

Measures:
  - Lines of code per ISA variant in hnswlib distance headers
    (parsed from #ifdef regions in space_l2.h / space_ip.h)
  - LOC and #ifdef count per file in FAISS's distance module
  - A summary comparison of the two strategies:
      hnswlib: single-file #ifdef soup
      FAISS:   separate compilation units per ISA

Outputs (in out/H4_run/):
  results.csv              raw counts (all rows)
  h4_loc_per_isa.png       LOC-per-ISA-variant comparison
  h4_ifdef_counts.png      #ifdef directive counts per file
"""

import argparse
import collections
import csv
import pathlib
import re

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_lines(path):
    with open(path) as f:
        return f.readlines()


def count_code_lines(lines):
    """Non-blank, non-comment LOC (handles // and /* */ comments)."""
    count = 0
    in_block = False
    for raw in lines:
        s = raw.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if "/*" in s:
            after = s[s.index("/*") + 2:]
            if "*/" not in after:
                in_block = True
                continue
        if not s or s.startswith("//"):
            continue
        count += 1
    return count


def count_preprocessor(lines):
    """Count #if / #ifdef / #elif / #ifndef directives."""
    pat = re.compile(r"^\s*#\s*(if|ifdef|elif|ifndef)\b")
    return sum(1 for l in lines if pat.match(l))


# ─────────────────────────────────────────────────────────────────────────────
# hnswlib: parse #ifdef regions, bucket LOC by ISA
# ─────────────────────────────────────────────────────────────────────────────

_IF_RE    = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b")
_ELIF_RE  = re.compile(r"^\s*#\s*elif\b")
_ELSE_RE  = re.compile(r"^\s*#\s*else\b")
_ENDIF_RE = re.compile(r"^\s*#\s*endif\b")


def _classify_guard(line):
    """
    Map an #if / #elif line to an ISA bucket name.
    Priority: AVX-512 > AVX/AVX2 > SSE > shared (combined) > other.
    """
    has_avx512 = "USE_AVX512" in line
    has_avx    = "USE_AVX"    in line.replace("USE_AVX512", "")
    has_sse    = "USE_SSE"    in line

    if has_avx512 and not has_avx and not has_sse:
        return "AVX-512"
    if has_avx and not has_avx512 and not has_sse:
        return "AVX/AVX2"
    if has_sse and not has_avx and not has_avx512:
        return "SSE"
    if has_avx512 or has_avx or has_sse:
        return "shared"
    return "other"


def parse_hnswlib_isa_loc(filepath):
    """
    Walk the file with a #if/#endif stack; bucket each non-blank,
    non-comment source line by its innermost ISA guard.
    Returns OrderedDict {label: loc_count}.
    """
    lines = read_lines(filepath)
    stack = ["Scalar"]          # baseline: unguarded code
    buckets = collections.defaultdict(int)
    in_block_comment = False

    for raw in lines:
        s = raw.strip()

        # ── block-comment tracking ────────────────────────────────────────
        if in_block_comment:
            if "*/" in s:
                in_block_comment = False
            continue
        if "/*" in s and "*/" not in s[s.index("/*") + 2:]:
            in_block_comment = True
            continue

        # ── preprocessor directives ───────────────────────────────────────
        if s.startswith("#"):
            if _IF_RE.match(raw):
                stack.append(_classify_guard(s))
            elif _ELIF_RE.match(raw):
                stack.pop()
                stack.append(_classify_guard(s))
            elif _ELSE_RE.match(raw):
                top = stack.pop()
                stack.append("else:" + top)
            elif _ENDIF_RE.match(raw):
                if len(stack) > 1:
                    stack.pop()
            continue

        # ── blank / single-line comment ───────────────────────────────────
        if not s or s.startswith("//"):
            continue

        buckets[stack[-1]] += 1

    # Canonical ordering
    order = ["Scalar", "SSE", "AVX/AVX2", "AVX-512", "shared", "other"]
    result = collections.OrderedDict()
    for k in order:
        if k in buckets:
            result[k] = buckets[k]
    for k, v in buckets.items():
        if k not in result:
            result[k] = v
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FAISS: file-level LOC and #ifdef count
# ─────────────────────────────────────────────────────────────────────────────

# (path relative to FAISS_DIR, human label, ISA)
FAISS_FILES = [
    ("faiss/utils/distances_simd.cpp",              "distances_simd.cpp",       "NONE (scalar)"),
    ("faiss/utils/simd_impl/distances_autovec-inl.h","distances_autovec-inl.h", "shared template"),
    ("faiss/utils/simd_impl/distances_sse-inl.h",   "distances_sse-inl.h",      "SSE helpers"),
    ("faiss/utils/simd_impl/distances_avx2.cpp",    "distances_avx2.cpp",       "AVX2"),
    ("faiss/utils/simd_impl/distances_avx512.cpp",  "distances_avx512.cpp",     "AVX-512"),
    ("faiss/utils/simd_impl/distances_aarch64.cpp", "distances_aarch64.cpp",    "ARM NEON"),
    ("faiss/utils/simd_impl/distances_arm_sve.cpp", "distances_arm_sve.cpp",    "ARM SVE"),
    ("faiss/utils/simd_levels.cpp",                 "simd_levels.cpp",          "ISA detection"),
]


def analyze_faiss(faiss_dir):
    rows = []
    for relpath, label, isa in FAISS_FILES:
        path = faiss_dir / relpath
        lines = read_lines(path)
        rows.append({
            "label":       label,
            "isa":         isa,
            "total_loc":   count_code_lines(lines),
            "ifdef_count": count_preprocessor(lines),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--out-dir", default="out/H4_run")
    args = ap.parse_args()

    root       = pathlib.Path(args.project_root).resolve()
    out_dir    = (root / args.out_dir).resolve()
    hnswlib_dir = root / "third_party" / "hnswlib"
    faiss_dir   = root / "faiss"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── hnswlib ──────────────────────────────────────────────────────────────
    hnswlib_files = {
        "space_l2.h":  hnswlib_dir / "space_l2.h",
        "space_ip.h":  hnswlib_dir / "space_ip.h",
        "hnswlib.h":   hnswlib_dir / "hnswlib.h",
    }

    hnswlib_results = {}
    for name, path in hnswlib_files.items():
        lines = read_lines(path)
        isa_loc = parse_hnswlib_isa_loc(path)
        hnswlib_results[name] = {
            "total_loc":   count_code_lines(lines),
            "ifdef_count": count_preprocessor(lines),
            "isa_loc":     isa_loc,
        }

    # ── FAISS ─────────────────────────────────────────────────────────────────
    faiss_results = analyze_faiss(faiss_dir)

    # ── Write CSV ─────────────────────────────────────────────────────────────
    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["library", "file", "isa_bucket", "loc", "ifdef_count"])

        for fname, data in hnswlib_results.items():
            total_ifdef = data["ifdef_count"]
            for isa, loc in data["isa_loc"].items():
                w.writerow(["hnswlib", fname, isa, loc, total_ifdef])

        for row in faiss_results:
            w.writerow(["FAISS", row["label"], row["isa"], row["total_loc"], row["ifdef_count"]])

    print(f"Wrote CSV: {csv_path}")

    # ── Print summary to stdout ───────────────────────────────────────────────
    print("\n=== hnswlib: LOC per ISA guard (space_l2.h + space_ip.h) ===")
    combined = collections.defaultdict(int)
    for fname in ("space_l2.h", "space_ip.h"):
        data = hnswlib_results[fname]
        print(f"\n  {fname}  (total LOC: {data['total_loc']}, "
              f"#ifdef directives: {data['ifdef_count']})")
        for isa, loc in data["isa_loc"].items():
            print(f"    {isa:20s}: {loc:4d} LOC")
            combined[isa] += loc

    print("\n  Combined (space_l2.h + space_ip.h):")
    for isa, loc in sorted(combined.items(), key=lambda x: -x[1]):
        print(f"    {isa:20s}: {loc:4d} LOC")

    hnswlib_total_ifdef = sum(
        hnswlib_results[f]["ifdef_count"]
        for f in ("space_l2.h", "space_ip.h", "hnswlib.h")
    )
    print(f"\n  Total #ifdef directives across all 3 hnswlib SIMD files: {hnswlib_total_ifdef}")

    print("\n=== FAISS: LOC and #ifdef per distance-module file ===")
    faiss_kernel_ifdef = 0
    for row in faiss_results:
        print(f"  {row['label']:40s} [{row['isa']:18s}]  "
              f"LOC: {row['total_loc']:5d}   #ifdef: {row['ifdef_count']:3d}")
        if row["label"] not in ("simd_levels.cpp",):
            faiss_kernel_ifdef += row["ifdef_count"]
    print(f"\n  Total #ifdef in kernel files (excl. detection): {faiss_kernel_ifdef}")

    # ── Plots ─────────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        print("matplotlib not available; skipping plots")
        return

    ISA_COLORS = {
        "Scalar":       "#6c757d",
        "SSE":          "#17a2b8",
        "AVX/AVX2":     "#28a745",
        "AVX-512":      "#fd7e14",
        "shared":       "#adb5bd",
        "other":        "#dee2e6",
    }

    # ── Plot 1: LOC per ISA variant ───────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("SIMD Developer Burden: Lines of Code per ISA Variant", fontsize=13)

    # Left: hnswlib grouped stacked bars (one group per file)
    hnsw_files  = ["space_l2.h", "space_ip.h"]
    isa_order   = ["Scalar", "SSE", "AVX/AVX2", "AVX-512", "shared"]
    x_hnsw      = np.arange(len(hnsw_files))
    bar_width   = 0.5
    bottoms     = np.zeros(len(hnsw_files))

    for isa in isa_order:
        heights = [
            hnswlib_results[f]["isa_loc"].get(isa, 0)
            for f in hnsw_files
        ]
        ax1.bar(x_hnsw, heights, bar_width, bottom=bottoms,
                label=isa, color=ISA_COLORS.get(isa, "#999"))
        bottoms += np.array(heights)

    ax1.set_xticks(x_hnsw)
    ax1.set_xticklabels(hnsw_files, fontsize=10)
    ax1.set_ylabel("Lines of Code (non-blank, non-comment)")
    ax1.set_title("hnswlib: single-file #ifdef approach\n(space_l2.h + space_ip.h)")
    ax1.legend(fontsize=8, loc="upper right")
    ax1.grid(axis="y", alpha=0.3)

    # Right: FAISS bar per file, coloured by ISA
    faiss_isa_color = {
        "NONE (scalar)":    ISA_COLORS["Scalar"],
        "shared template":  ISA_COLORS["shared"],
        "SSE helpers":      ISA_COLORS["SSE"],
        "AVX2":             ISA_COLORS["AVX/AVX2"],
        "AVX-512":          ISA_COLORS["AVX-512"],
        "ARM NEON":         "#6610f2",
        "ARM SVE":          "#e83e8c",
        "ISA detection":    "#343a40",
    }
    f_labels = [r["label"]  for r in faiss_results]
    f_locs   = [r["total_loc"] for r in faiss_results]
    f_colors = [faiss_isa_color.get(r["isa"], "#999") for r in faiss_results]
    x_faiss  = np.arange(len(f_labels))

    bars = ax2.bar(x_faiss, f_locs, color=f_colors, edgecolor="white", linewidth=0.5)
    ax2.set_xticks(x_faiss)
    ax2.set_xticklabels(
        [l.replace("distances_", "dist_") for l in f_labels],
        rotation=30, ha="right", fontsize=8,
    )
    ax2.set_ylabel("Lines of Code (non-blank, non-comment)")
    ax2.set_title("FAISS: separate-file-per-ISA approach\n(distance module files)")
    ax2.grid(axis="y", alpha=0.3)

    # Add value labels on FAISS bars
    for bar, val in zip(bars, f_locs):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                 str(val), ha="center", va="bottom", fontsize=7)

    # Colour legend for FAISS
    from matplotlib.patches import Patch
    legend_items = [
        Patch(color=faiss_isa_color[isa], label=isa)
        for isa in faiss_isa_color
        if any(r["isa"] == isa for r in faiss_results)
    ]
    ax2.legend(handles=legend_items, fontsize=7, loc="upper right")

    plt.tight_layout()
    p1 = out_dir / "h4_loc_per_isa.png"
    plt.savefig(p1, dpi=150)
    plt.close()
    print(f"\nWrote plot: {p1}")

    # ── Plot 2: #ifdef directive counts (horizontal bar) ──────────────────────
    all_files  = []
    all_counts = []
    all_colors = []

    for fname, data in hnswlib_results.items():
        all_files.append(f"hnswlib / {fname}")
        all_counts.append(data["ifdef_count"])
        all_colors.append("#0d6efd")

    for row in faiss_results:
        all_files.append(f"FAISS / {row['label']}")
        all_counts.append(row["ifdef_count"])
        all_colors.append("#dc3545" if row["label"] == "simd_levels.cpp" else "#fd7e14")

    # Reverse so top of chart = first entry
    all_files  = all_files[::-1]
    all_counts = all_counts[::-1]
    all_colors = all_colors[::-1]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.set_title("#ifdef Directive Count per File\n"
                 "(lower = less ISA-conditional branching in source)", fontsize=12)

    y = np.arange(len(all_files))
    bars2 = ax.barh(y, all_counts, color=all_colors, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(all_files, fontsize=9)
    ax.set_xlabel("Number of #if / #ifdef / #elif / #ifndef directives")
    ax.grid(axis="x", alpha=0.3)

    for bar, val in zip(bars2, all_counts):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                str(val), ha="left", va="center", fontsize=9)

    ax.set_xlim(0, max(all_counts) * 1.22)

    from matplotlib.patches import Patch
    legend_items2 = [
        Patch(color="#0d6efd", label="hnswlib (kernel files)"),
        Patch(color="#fd7e14", label="FAISS (kernel files)"),
        Patch(color="#dc3545", label="FAISS simd_levels.cpp (detection)"),
    ]
    ax.legend(handles=legend_items2, fontsize=9, loc="upper right")

    plt.tight_layout()
    p2 = out_dir / "h4_ifdef_counts.png"
    plt.savefig(p2, dpi=150)
    plt.close()
    print(f"Wrote plot: {p2}")


if __name__ == "__main__":
    main()
