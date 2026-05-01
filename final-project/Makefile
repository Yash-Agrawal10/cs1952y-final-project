HOST_CXX  = g++
RISCV_CXX = riscv64-unknown-elf-g++

COMMON_CXXFLAGS = -std=c++17 -O2 -Wall -Wextra -static
HOST_CXXFLAGS   = $(COMMON_CXXFLAGS)
RISCV_CXXFLAGS  = $(COMMON_CXXFLAGS) -DGEM5_M5OPS
# Maybe investigate how we enable simd closer
RISCV_SIMD_CXXFLAGS = $(RISCV_CXXFLAGS) -march=rv64gcv -ftree-vectorize -mrvv-max-lmul=m1

SRC            = src
INCLUDES       = -I$(SRC)
HOST_INCLUDES  = $(INCLUDES) -isystem third_party
RISCV_INCLUDES = $(INCLUDES)

HOST_BIN  = binaries/host
RISCV_BIN = binaries/riscv

GEM5       ?= /gem5_build/gem5.debug
SIM_OUT    ?= out
# Extra arguments passed to run.py for simulations
EXTRA_ARGS ?=

.PHONY: all host riscv clean sim-flat sim-flat-simd sim-hnsw sim-hnsw-simd clean-sim

all: host riscv

host: $(HOST_BIN)/gen_data \
      $(HOST_BIN)/flat_search \
	  $(HOST_BIN)/hnsw_search

riscv: $(RISCV_BIN)/flat_search \
       $(RISCV_BIN)/flat_search_simd \
       $(RISCV_BIN)/hnsw_search \
       $(RISCV_BIN)/hnsw_search_simd

$(HOST_BIN)/gen_data: $(SRC)/host/gen_data.cpp
	@mkdir -p $(HOST_BIN)
	$(HOST_CXX) $(HOST_CXXFLAGS) $(HOST_INCLUDES) $< -o $@

$(HOST_BIN)/flat_search: $(SRC)/flat_search.cpp
	@mkdir -p $(HOST_BIN)
	$(HOST_CXX) $(HOST_CXXFLAGS) $(HOST_INCLUDES) $< -o $@

$(RISCV_BIN)/flat_search: $(SRC)/flat_search.cpp
	@mkdir -p $(RISCV_BIN)
	$(RISCV_CXX) $(RISCV_CXXFLAGS) $(RISCV_INCLUDES) $< -o $@

$(RISCV_BIN)/flat_search_simd: $(SRC)/flat_search.cpp
	@mkdir -p $(RISCV_BIN)
	$(RISCV_CXX) $(RISCV_SIMD_CXXFLAGS) $(RISCV_INCLUDES) $< -o $@

$(HOST_BIN)/hnsw_search: $(SRC)/hnsw_search.cpp
	@mkdir -p $(HOST_BIN)
	$(HOST_CXX) $(HOST_CXXFLAGS) $(HOST_INCLUDES) $< -o $@

$(RISCV_BIN)/hnsw_search: $(SRC)/hnsw_search.cpp
	@mkdir -p $(RISCV_BIN)
	$(RISCV_CXX) $(RISCV_CXXFLAGS) $(RISCV_INCLUDES) $< -o $@

$(RISCV_BIN)/hnsw_search_simd: $(SRC)/hnsw_search.cpp
	@mkdir -p $(RISCV_BIN)
	$(RISCV_CXX) $(RISCV_SIMD_CXXFLAGS) $(RISCV_INCLUDES) $< -o $@

clean:
	rm -rf binaries

sim-flat: $(RISCV_BIN)/flat_search
	$(GEM5) -d $(SIM_OUT)/flat configs/run.py --binary binaries/riscv/flat_search $(EXTRA_ARGS)

sim-flat-simd: $(RISCV_BIN)/flat_search_simd
	$(GEM5) -d $(SIM_OUT)/flat_simd configs/run.py --binary binaries/riscv/flat_search_simd $(EXTRA_ARGS)

sim-hnsw: $(RISCV_BIN)/hnsw_search
	$(GEM5) -d $(SIM_OUT)/hnsw configs/run.py --binary binaries/riscv/hnsw_search $(EXTRA_ARGS)

sim-hnsw-simd: $(RISCV_BIN)/hnsw_search_simd
	$(GEM5) -d $(SIM_OUT)/hnsw_simd configs/run.py --binary binaries/riscv/hnsw_search_simd $(EXTRA_ARGS)

clean-sim:
	rm -rf $(SIM_OUT)
