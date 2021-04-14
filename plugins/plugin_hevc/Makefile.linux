
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

PROGDIR?= ./HM-master

.PHONY: default
default: zip dir hevc clean

zip:
	unzip HM-master.zip

dir:
	mkdir $(PROGDIR)/dir
	cp $(PROGDIR)/CMakeLists.txt $(PROGDIR)/dir


hevc:
	cd $(PROGDIR)/dir && echo "I'm in dir" && \
	cmake -DCMAKE_BUILD_TYPE=Release -DHIGH_BITDEPTH=ON .. && \
	make
	cp $(PROGDIR)/bin/TAppEncoderStatic ./
	cp $(PROGDIR)/bin/TAppDecoderStatic ./

clean:
	rm -rf HM-master