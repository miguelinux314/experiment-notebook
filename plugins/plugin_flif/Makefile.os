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

PROGDIR?= ./lib

.PHONY: default
default: zip dependences flif clean

zip:
	unzip flif_0.3_2017.zip

dependences:
	brew install pkg-config libpng sdl2

flif:
	cd $(PROGDIR) && $(MAKE)
	cd $(PROGDIR)/src && \
	cp flif ../../

clean:
	rm -rf lib