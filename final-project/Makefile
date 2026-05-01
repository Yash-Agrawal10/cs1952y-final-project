HOST_CXX  = g++
RISCV_CXX = riscv64-unknown-elf-g++

CXXFLAGS = -std=c++17 -O2 -Wall -Wextra -static

SRC           = src
INCLUDES      = -I$(SRC) -isystem third_party

HOST_BIN  = binaries/host
RISCV_BIN = binaries/riscv

GEM5    ?= /gem5_build/gem5.debug
SIM_OUT ?= out

.PHONY: all host riscv clean sim-flat sim-hnsw clean-sim

all: host riscv

host: $(HOST_BIN)/gen_data \
      $(HOST_BIN)/flat_search \
	  $(HOST_BIN)/hnsw_search

riscv: $(RISCV_BIN)/flat_search \
       $(RISCV_BIN)/hnsw_search

$(HOST_BIN)/gen_data: $(SRC)/host/gen_data.cpp
	@mkdir -p $(HOST_BIN)
	$(HOST_CXX) $(CXXFLAGS) $(INCLUDES) $< -o $@

$(HOST_BIN)/flat_search: $(SRC)/flat_search.cpp
	@mkdir -p $(HOST_BIN)
	$(HOST_CXX) $(CXXFLAGS) $(INCLUDES) $< -o $@

$(RISCV_BIN)/flat_search: $(SRC)/flat_search.cpp
	@mkdir -p $(RISCV_BIN)
	$(RISCV_CXX) $(CXXFLAGS) $(INCLUDES) $< -o $@

$(HOST_BIN)/hnsw_search: $(SRC)/hnsw_search.cpp
	@mkdir -p $(HOST_BIN)
	$(HOST_CXX) $(CXXFLAGS) $(INCLUDES) $< -o $@

$(RISCV_BIN)/hnsw_search: $(SRC)/hnsw_search.cpp
	@mkdir -p $(RISCV_BIN)
	$(RISCV_CXX) $(CXXFLAGS) $(INCLUDES) $< -o $@

clean:
	rm -rf binaries

sim-flat: $(RISCV_BIN)/flat_search
	$(GEM5) -d $(SIM_OUT)/flat configs/run.py --binary binaries/riscv/flat_search

sim-hnsw: $(RISCV_BIN)/hnsw_search
	$(GEM5) -d $(SIM_OUT)/hnsw configs/run.py --binary binaries/riscv/hnsw_search

clean-sim:
	rm -rf $(SIM_OUT)
