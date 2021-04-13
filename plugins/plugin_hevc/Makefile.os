CFLAGS += -std=gnu++11 -Wall -Wextra -Wcast-qual -Wcast-align -Wstrict-aliasing=1 -Wswitch-enum -Wundef -pedantic  -Wfatal-errors -Werror

CFLAGS += -I./src

CFLAGS += `pkg-config opencv --cflags`
LFLAGS += `pkg-config opencv --libs`

LFLAGS += -lboost_system -lboost_program_options -lboost_serialization
LFLAGS += -lz -lrt
LFLAGS += -lsnappy -lCharLS -lzstd -llz4 -llzo2


CFLAGS += -fopenmp
LFLAGS += -lgomp

CFLAGS += -Ofast

CFLAGS += -g

CFLAGS += -I./ext
LFLAGS += $(wildcard ./ext/*.a)


#CFLAGS += -DNDEBUG
#CFLAGS += -frename-registers -fopenmp
#CFLAGS += -fno-unroll-loops
#CFLAGS += -funroll-all-loops
#CFLAGS += -fno-align-loops
#CFLAGS += -fno-align-labels
#CFLAGS += -fno-tree-vectorize
#CFLAGS += -falign-functions -falign-labels -falign-jumps -falign-loops -frename-registers -finline-functions
#CFLAGS += -fomit-frame-pointer
#CFLAGS += -fmerge-all-constants -fmodulo-sched -fmodulo-sched-allow-regmoves -funsafe-loop-optimizations -floop-unroll-and-jam

BUILD_SCRIPT := $(CURDIR)/cmake/CMakeBuild/bin/cmake.py

ifeq ($(OS),Windows_NT)
  ifneq ($(MSYSTEM),)
    # MSYS runtime environment
    UNAME_S := $(shell uname -s)
    PYTHON_LAUNCHER := python3
    BUILD_CMD := $(PYTHON_LAUNCHER) $(BUILD_SCRIPT)
  else
    UNAME_S := Windows
    PY := $(wildcard c:/windows/py.*)
    ifeq ($(PY),)
      PYTHON_LAUNCHER := python
    else
      PYTHON_LAUNCHER := $(notdir $(PY))
    endif
    # If a plain cmake.py is used, the exit codes won't arrive in make; i.e. build failures are reported as success by make.
    BUILD_CMD := $(PYTHON_LAUNCHER) $(BUILD_SCRIPT)
    ifeq ($(toolset),gcc)
      g := mgwmake
    endif
  endif
else
  UNAME_S := $(shell uname -s)
  BUILD_CMD := $(BUILD_SCRIPT)
  ifeq ($(UNAME_S),Linux)
    # for Jenkins: run trace build only on Linux
    LINUXBUILD := TRUE
  endif
  ifeq ($(UNAME_S),Darwin)
    # MAC
  endif
endif

PROGDIR?= ./HM-master

.PHONY: default
default: zip dependences hevc rename clean

zip:
	unzip HM-master.zip

dependences:
	brew install cmake

hevc:
	mkdir $(PROGDIR)/dir
	cd $(PROGDIR)/dir && echo "I'm in dir" && \
	cmake .. -DCMAKE_BUILD_TYPE=Release -DHIGH_BITDEPTH=ON && \
	$(MAKE)
	find $(PROGDIR)/bin -type f -name "TAppEncoder" -exec cp "{}" ./ \;
	find $(PROGDIR)/bin -type f -name "TAppDecoder" -exec cp "{}" ./ \;

rename:
	mv TAppEncoder TAppEncoderStatic
	mv TAppDecoder TAppDecoderStatic

clean:
	rm -rf HM-master
