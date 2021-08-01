# #####################################################################
# FSE - tester Makefile
# Copyright (C) Yann Collet 2013-present
# GPL v2 License
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# You can contact the author at :
#  - Public forum froup : https://groups.google.com/forum/#!forum/lz4c
# #####################################################################
# fse : Command Line Utility, featuring benchmark and validation tools
# fuzzer : stress tester for FSE library
# fuzzerHuff0 : stress tester for Huff0 library
# #####################################################################

RELEASE    = v0.3.4
FSEDIR     = ./fse_git/lib
PROGDIR?= ./fse_git/programs


ifeq ($(shell $(CC) -v 2>&1 | grep -c "gcc version "), 1)
ALIGN_LOOP = # -falign-functions=16 # -falign-loops=32
else
ALIGN_LOOP =
endif

DESTDIR   ?=
CPPFLAGS  += -I$(FSEDIR)
CFLAGS    ?= -O3 $(ALIGN_LOOP)
CFLAGS    += -Wall -Wextra -Wcast-qual -Wcast-align -Wshadow \
			 -Wstrict-aliasing=1 -Wswitch-enum -Wstrict-prototypes -Wundef
FLAGS      = $(CPPFLAGS) $(CFLAGS) $(LDFLAGS) $(MOREFLAGS)
FSETEST   ?=
FSEU16TEST?= $(FSETEST)

# Define *.exe as extension for Windows systems
ifneq (,$(filter Windows%,$(OS)))
EXT =.exe
else
EXT =
endif


.PHONY: default
default: fse_git fse

.PHONY: all
all: fse_git fse fullbench fuzzer fuzzerU16 fuzzerHuff0 probagen


fse_git:
	unzip fse_git.zip

fse: $(PROGDIR)/bench.c $(PROGDIR)/commandline.c $(PROGDIR)/fileio.c $(PROGDIR)/xxhash.c $(PROGDIR)/zlibh.c \
				  $(FSEDIR)/entropy_common.c $(FSEDIR)/hist.c \
				  $(FSEDIR)/fse_decompress.c $(FSEDIR)/fse_compress.c $(FSEDIR)/fseU16.c \
				  $(FSEDIR)/huf_compress.c $(FSEDIR)/huf_decompress.c
	$(CC) $(FLAGS) $^ -o $@$(EXT)
	rm -rf fse_git

fse_opt:
	$(MAKE) fse MOREFLAGS=-flto

fuzzer: CPPFLAGS += -DDEBUGLEVEL=1
fuzzer: $(PROGDIR)/fuzzer.c $(PROGDIR)/xxhash.c $(FSEDIR)/entropy_common.c $(FSEDIR)/hist.c \
				 $(FSEDIR)/fse_decompress.c $(FSEDIR)/fse_compress.c
	$(CC) $(FLAGS) $^ -o $@$(EXT)

fuzzerU16: CPPFLAGS += -DDEBUGLEVEL=1
fuzzerU16: fuzzerU16.c xxhash.c $(FSEDIR)/entropy_common.c $(FSEDIR)/hist.c \
						$(FSEDIR)/fse_decompress.c $(FSEDIR)/fse_compress.c $(FSEDIR)/fseU16.c
	$(CC) $(FLAGS) $^ -o $@$(EXT)

fuzzerHuff0: CPPFLAGS += -DDEBUGLEVEL=1
fuzzerHuff0: fuzzerHuff0.c xxhash.c $(FSEDIR)/entropy_common.c $(FSEDIR)/hist.c \
							$(FSEDIR)/huf_compress.c $(FSEDIR)/huf_decompress.c \
							$(FSEDIR)/fse_decompress.c $(FSEDIR)/fse_compress.c
	$(CC) $(FLAGS) $^ -o $@$(EXT)

fullbench: fullbench.c xxhash.c $(FSEDIR)/entropy_common.c $(FSEDIR)/hist.c \
									$(FSEDIR)/fse_decompress.c $(FSEDIR)/fse_compress.c $(FSEDIR)/fseU16.c \
									$(FSEDIR)/huf_compress.c $(FSEDIR)/huf_decompress.c
	$(CC) $(FLAGS) $^ -o $@$(EXT)

probagen: $(PROGDIR)/probaGenerator.c
	$(CC) $(FLAGS) $^ -o $@$(EXT)

.PHONY: clean
clean:
	@$(RM) fse$(EXT) fullbench$(EXT) probagen$(EXT)
	@$(RM) fuzzer$(EXT) fuzzerU16$(EXT) fuzzerHuff0$(EXT)
	@$(RM) core *.o tmp result proba.bin
	@$(RM) -rf fse_git
	@echo Cleaning completed


.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$' | xargs

test-fse: probagen fse
	./probagen 20%
	@echo "**** compress using FSE ****"
	./fse -f proba.bin tmp
	./fse -df tmp result
	diff proba.bin result
	@echo "**** compress using HUF ****"
	./fse -fh proba.bin tmp
	./fse -df tmp result
	diff proba.bin result
	@echo "**** compress using zlibh ****"
	./fse -fz proba.bin tmp
	./fse -df tmp result
	diff proba.bin result
	rm result
	rm proba.bin
	rm tmp
	rm probagen

check: test-fse

test: test-fse fullbench fuzzer fuzzerU16 fuzzerHuff0
	./fuzzer $(FSETEST)
	./fullbench -i1
	./fuzzerU16 $(FSEU16TEST)
	./fuzzerHuff0 $(FSETEST)

memtest: fuzzer fullbench fuzzerU16 fuzzerHuff0
	valgrind --version
	valgrind --leak-check=yes --error-exitcode=1 ./fuzzer -i256
	valgrind --leak-check=yes --error-exitcode=1 ./fullbench -i1
	valgrind --leak-check=yes --error-exitcode=1 ./fuzzerU16 -i128
	valgrind --leak-check=yes --error-exitcode=1 ./fuzzerHuff0 -i256

test-all: test test32 memtest
	@echo test completed
