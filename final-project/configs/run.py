"""
run.py — single runnable config that drives all final-project experiments.

Thin wrapper around base.make_system. Every knob is a CLI flag declared in
base.py; see that file for the full list and defaults.

Hypothesis -> knob:
    H1 (SIMD)        vary --binary  (e.g. flat_scalar vs flat_vec)
    H2 (cache size)  vary --l2_size,
    H3 (OoO/inorder) vary --cpu_type {o3, minor}

Example:
    gem5.debug --outdir=m5out/smoke run.py --binary binaries/test

Flags currently exposed (typical values shown in {}):
    --binary     {binaries/test, binaries/flat_scalar, binaries/flat_vec,
                  binaries/hnsw_scalar, binaries/hnsw_vec}
    --cpu_type   {o3, minor, timing_simple}
    --mem_size   {512MB, 1GB, 4GB, 8GB}
    --l1i_size   {16kB, 32kB, 64kB}
    --l1d_size   {16kB, 32kB, 64kB}
    --l2_size    {64kB, 256kB, 1MB, 4MB}
    --l2_assoc   {1, 2, 4, 8, 16}
"""

import m5
from m5.objects import Root

# Make `from common import SimpleOpts` resolvable. Same path as base.py uses.
m5.util.addToPath("../../configs")
from common import SimpleOpts
from base import make_system

args = SimpleOpts.parse_args()
system = make_system(args)

root = Root(full_system=False, system=system)
m5.instantiate()

print("Beginning simulation!")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
