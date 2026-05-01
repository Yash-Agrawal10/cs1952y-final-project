"""
base.py — shared system-construction helpers for final-project configs.

This module defines:
  - L1ICache, L1DCache, L2Cache classes (Cache subclasses with sensible defaults)
  - CLI options (--binary, --cpu_type, --l1d_size, --l2_size, ...)
  - make_system(args): builds and returns a fully wired System

Runnable configs (o3.py, inorder.py, cache_sweep.py, ...) import from here.
"""

import os
import m5
from m5.objects import *

# `configs/common/SimpleOpts.py` lives two levels up from this file
# (final-project/configs/base.py -> repo_root/configs/common/SimpleOpts.py).
m5.util.addToPath("../../configs")
from common import SimpleOpts


# CLI options. Registered at module-import time so every config that does
# `from base import ...` automatically inherits them.
SimpleOpts.add_option(
    "--binary", required=True,
    help="Path to the RISC-V binary, relative to final-project/")
SimpleOpts.add_option(
    "--cpu_type", default="o3",
    choices=["o3", "minor", "timing_simple"],
    help="CPU model: o3 (OoO), minor (in-order pipelined), timing_simple (toy)")
SimpleOpts.add_option(
    "--mem_size", default="4GB",
    help="Total simulated DRAM size")
SimpleOpts.add_option(
    "--l1i_size", default="32kB", help="L1 instruction cache size")
SimpleOpts.add_option(
    "--l1d_size", default="32kB", help="L1 data cache size")
SimpleOpts.add_option(
    "--l2_size", default="256kB",
    help="L2 cache size — the H2 sweep variable")
SimpleOpts.add_option(
    "--l2_assoc", default=8, type=int, help="L2 associativity")


# Cache classes. Subclassing m5.objects.Cache lets us bake in a default
# latency/MSHR profile, then per-instance overrides come from CLI args.
class L1ICache(Cache):
    assoc            = 4
    tag_latency      = 2
    data_latency     = 2
    response_latency = 2
    mshrs            = 4
    tgts_per_mshr    = 20

    def __init__(self, args):
        super().__init__()
        self.size = args.l1i_size

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1DCache(Cache):
    assoc            = 4
    tag_latency      = 2
    data_latency     = 2
    response_latency = 2
    mshrs            = 4
    tgts_per_mshr    = 20

    def __init__(self, args):
        super().__init__()
        self.size = args.l1d_size

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L2Cache(Cache):
    tag_latency      = 20
    data_latency     = 20
    response_latency = 20
    mshrs            = 20
    tgts_per_mshr    = 12

    def __init__(self, args):
        super().__init__()
        self.size  = args.l2_size
        self.assoc = args.l2_assoc

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports


# CPU factory. Centralizing this means H3 (OoO vs in-order) is a one-line
# change in the runnable config: just pass a different --cpu_type.
def _make_cpu(cpu_type):
    if cpu_type == "o3":
        return RiscvO3CPU1952y()
    if cpu_type == "minor":
        return RiscvMinorCPU()
    if cpu_type == "timing_simple":
        return RiscvTimingSimpleCPU()
    raise ValueError(f"unknown cpu_type: {cpu_type}")


# Builder. Returns a fully configured System ready for m5.instantiate().
def make_system(args):
    system = System()

    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = "1GHz"
    system.clk_domain.voltage_domain = VoltageDomain()

    system.mem_mode   = "timing"
    system.mem_ranges = [AddrRange(args.mem_size)]

    # CPU
    system.cpu = _make_cpu(args.cpu_type)

    # L1 caches, attached directly to CPU ports
    system.cpu.icache = L1ICache(args)
    system.cpu.dcache = L1DCache(args)
    system.cpu.icache.connectCPU(system.cpu)
    system.cpu.dcache.connectCPU(system.cpu)

    # Both L1s share an L2 bus, which feeds into the unified L2 cache.
    system.l2bus = L2XBar()
    system.cpu.icache.connectBus(system.l2bus)
    system.cpu.dcache.connectBus(system.l2bus)

    system.l2cache = L2Cache(args)
    system.l2cache.connectCPUSideBus(system.l2bus)

    # The L2 talks to the system's main memory bus, which fronts DRAM.
    system.membus = SystemXBar()
    system.l2cache.connectMemSideBus(system.membus)

    system.cpu.createInterruptController()

    system.mem_ctrl           = MemCtrl()
    system.mem_ctrl.dram      = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port      = system.membus.mem_side_ports

    # Lets gem5 itself read/write memory (e.g. to load the ELF segments).
    system.system_port = system.membus.cpu_side_ports

    # Resolve binary and data paths to absolute. Absolute paths in process.cmd
    # mean SE-mode file I/O works regardless of where gem5 was launched from.
    thispath     = os.path.dirname(os.path.realpath(__file__))
    project_root = os.path.realpath(os.path.join(thispath, ".."))
    bin_path     = os.path.join(project_root, args.binary)
    data_dir     = os.path.join(project_root, "data")

    # Common to both search binaries; dispatch on binary name for the rest.
    cmd = [bin_path, "--queries", os.path.join(data_dir, "queries.bin")]
    bin_name = os.path.basename(args.binary)
    if "flat" in bin_name:
        cmd += ["--vectors", os.path.join(data_dir, "vectors.bin")]
    elif "hnsw" in bin_name:
        cmd += ["--hnsw", os.path.join(data_dir, "hnsw.bin")]

    system.workload = SEWorkload.init_compatible(bin_path)
    process = Process()
    process.cmd = cmd
    system.cpu.workload = process
    system.cpu.createThreads()

    return system
