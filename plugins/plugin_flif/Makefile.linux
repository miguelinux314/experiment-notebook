PREFIX := $(DESTDIR)/usr/local
CXXFLAGS := $(CXXFLAGS) $(shell pkg-config --cflags zlib libpng) -DLODEPNG_NO_COMPILE_PNG -DLODEPNG_NO_COMPILE_DISK
CFLAGS := $(CFLAGS) $(shell pkg-config --cflags zlib libpng) -DLODEPNG_NO_COMPILE_PNG -DLODEPNG_NO_COMPILE_DISK
LDFLAGS := $(LDFLAGS) $(shell pkg-config --libs libpng)

OSNAME := $(shell uname -s)
SONAME = -soname
LIBEXT = .so
SOVERSION = 0
LIBEXTV = $(LIBEXT).$(SOVERSION)
ifeq ($(OSNAME),Darwin)
  SONAME = -install_name
  LIBEXT = .dylib
  LIBEXTV = .$(SOVERSION)$(LIBEXT)
endif

# for running interface-test
export LD_LIBRARY_PATH := $(shell pwd):/usr/local/lib:$(LD_LIBRARY_PATH)

FILES_H := lib/src/maniac/*.hpp maniac/*.cpp lib/src/image/*.hpp transform/*.hpp lib/src/flif-enc.hpp lib/src/flif-dec.hpp lib/src/common.hpp lib/src/flif_config.h lib/src/fileio.hpp lib/src/io.hpp lib/src/io.cpp lib/src/config.h lib/src/compiler-specific.hpp lib/extern/lodepng.h
FILES_CPP := lib/src/maniac/chance.cpp lib/src/maniac/symbol.cpp lib/src/image/crc32k.cpp lib/src/image/image.cpp lib/src/image/image-png.cpp lib/src/image/image-pnm.cpp lib/src/image/image-pam.cpp lib/src/image/image-rggb.cpp lib/src/image/image-metadata.cpp lib/src/image/color_range.cpp lib/src/transform/factory.cpp common.cpp flif-enc.cpp lib/src/flif-dec.cpp io.cpp lib/extern/lodepng.cpp
FILES_O := lib/src/maniac/chance.o lib/src/maniac/symbol.o lib/src/image/crc32k.o lib/src/image/image.o lib/src/image/image-png.o lib/src/image/image-pnm.o lib/src/image/image-pam.o lib/src/image/image-rggb.o lib/src/image/image-metadata.o lib/src/image/color_range.o lib/src/transform/factory.o lib/src/common.o lib/src/flif-enc.o lib/src/flif-dec.o lib/src/io.o lib/extern/lodepng.o

.PHONY: default
default: zip flif libflif$(LIBEXT)

# options to consider: -fvect-cost-model=unlimited -funroll-all-loops
OPTIMIZATIONS := -DNDEBUG -O2 -ftree-vectorize
# there are often problems with clang and lto also it doesn't seem to know -fwhole-program
ifeq ($(CXX), g++)
	OPTIMIZATIONS := $(OPTIMIZATIONS) -flto
endif

LIB_OPTIMIZATIONS := -DNDEBUG -O2
ifeq ($(CXX), g++)
	LIB_OPTIMIZATIONS := $(LIB_OPTIMIZATIONS) -flto
endif

zip:
	unzip flif_0.3_2017.zip

# This is how .cpp files are compiled to .o files
.cpp.o:
	$(CXX) -c -std=gnu++11 $(CPPFLAGS) $(CXXFLAGS) $(OPTIMIZATIONS) -Wall -fPIC -o $*.o $*.cpp

# Command-line FLIF encoding/decoding tool - LGPLv3
flif: $(FILES_O) lib/src/flif.o
	$(CXX) -std=gnu++11 $(CXXFLAGS) $(CPPFLAGS) $(LIB_OPTIMIZATIONS) -Wall -fPIC -o flif lib/src/flif.o $(FILES_O) $(LDFLAGS)

# Decoder + encoder library - LGPL
libflif$(LIBEXT): $(FILES_O) lib/src/library/flif-interface.o
	$(CXX) -shared -std=gnu++11 $(CPPFLAGS) $(CXXFLAGS) $(LIB_OPTIMIZATIONS) -Wall -fPIC -o libflif$(LIBEXTV) $(FILES_O) lib/src/library/flif-interface.o -Wl,$(SONAME),libflif$(LIBEXTV) $(LDFLAGS)
	rm -rf lib
	rm libflif.so.0

# Example application: simple FLIF viewer - public domain
viewflif: libflif$(LIBEXT) viewflif.c
	$(CC) -std=gnu11 $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) -O3 $(shell sdl2-config --cflags) -Wall -Ilibrary/ viewflif.c -L. -lflif $(shell sdl2-config --libs) -o viewflif

# gdk-pixbuf loader, enabling FLIF-viewing in pixbuf applications like Eye of Gnome
# -Werror=implicit-function-declaration is useful here to check for preprocessor dependency errors
libpixbufloader-flif$(LIBEXT): libflif$(LIBEXT) flif-pixbuf-loader.c
	$(CC) -shared $(CFLAGS) -Ilibrary/ -fPIC -Wall -Werror=implicit-function-declaration $(shell pkg-config --cflags gdk-pixbuf-2.0) -o libpixbufloader-flif$(LIBEXT) flif-pixbuf-loader.c $(LDFLAGS) $(shell pkg-config --libs gdk-pixbuf-2.0) -L. -lflif

pixbufloader: libpixbufloader-flif$(LIBEXT)

install: flif libflif$(LIBEXT) install-libflif$(LIBEXT)
	install -d $(PREFIX)/bin $(PREFIX)/share/man/man1
	install -m 755 flif $(PREFIX)/bin
	strip -x $(PREFIX)/bin/flif
	install -m 644 ../doc/flif.1 $(PREFIX)/share/man/man1
	install -m 755 ../tools/gif2flif $(PREFIX)/bin
	install -m 755 ../tools/apng2flif $(PREFIX)/bin

install-viewflif:
	install -m 755 viewflif $(PREFIX)/bin
	strip -x $(PREFIX)/bin/viewflif

install-libflif$(LIBEXT): libflif$(LIBEXT)
	install -d $(PREFIX)/lib
	install -m 755 libflif$(LIBEXT) libflif$(LIBEXTV) $(PREFIX)/lib
	strip -x $(PREFIX)/lib/libflif$(LIBEXT) \
	  $(PREFIX)/lib/libflif$(LIBEXTV)

# There is no prefix here because gdk-pixbuf will not search /usr/local for loadrs
# while it sucks, it's the truth
install-libpixbufloader-flif$(LIBEXT): libpixbufloader-flif$(LIBEXT) install-libflif$(LIBEXT)
	install -c -d /usr/lib/gdk-pixbuf-2.0/2.10.0/loaders
	install -c -m 755 -s libpixbufloader-flif$(LIBEXT) /usr/lib/gdk-pixbuf-2.0/2.10.0/loaders/
	gdk-pixbuf-query-loaders --update-cache
	xdg-mime install --novendor flif-mime.xml

install-pixbufloader: install-libpixbufloader-flif$(LIBEXT)

install-dev:
	install -d $(PREFIX)/include
	install -m 644 library/*.h $(PREFIX)/include

magic:
	if ! grep -q FLIF /etc/magic; then cat ../doc/flif.magic >> /etc/magic; fi

uninstall:
	rm -f $(PREFIX)/bin/flif
	rm -f $(PREFIX)/bin/viewflif
	rm -f $(PREFIX)/bin/gif2flif
	rm -f $(PREFIX)/bin/apng2flif
	rm -f $(PREFIX)/include/flif.h
	rm -f $(PREFIX)/include/flif_common.h
	rm -f $(PREFIX)/include/flif_dec.h
	rm -f $(PREFIX)/include/flif_enc.h
	rm -f $(PREFIX)/lib/libflif$(LIBEXT)
	rm -f $(PREFIX)/lib/libflif$(LIBEXTV)
	rm -f $(PREFIX)/share/man/man1/flif.1
	rm -f /usr/lib/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-flif$(LIBEXT)

clean:
	rm -f flif dflif lib*flif*$(LIBEXT)* viewflif flif.asan flif.dbg flif.prof flif.stats test-interface $(FILES_O) lib/src/flif.o lib/src/library/flif-interface.o lib/


# The targets below are only meant for developers

test-interface: libflif.dbg$(LIBEXT) libflif$(LIBEXT) ../tools/test.c
	$(CC) -O0 -ggdb3 -Wall -Ilibrary/ ../tools/test.c -L. -lflif.dbg  -o test-interface

test: flif test-interface
	mkdir -p ../tmp-test
	./test-interface ../tmp-test/dummy.flif
	../tools/test-roundtrip.sh ./flif ../tools/2_webp_ll.png ../tmp-test/2_webp_ll.flif ../tmp-test/decoded_2_webp_ll.png
	../tools/test-roundtrip.sh ./flif ../tools/kodim01.png ../tmp-test/kodim01.flif ../tmp-test/decoded_kodim01.png
	../tools/test-lossy.sh ./flif ../tools/kodim01.png ../tmp-test/kodim01-lossy.flif ../tmp-test/decoded_kodim01-lossy.png
	../tools/test-roundtrip_anim.sh ./flif ../tools/endless_war.gif ../tmp-test/endless_war.flif
	../tools/test-roundtrip_anim_framedir.sh ./flif ../tools/bouncing_ball_frames ../tmp-test/bouncing_ball.flif
	../tools/test-metadata.sh ./flif ../testFiles/sig05-014.png ../tmp-test/out-meta.flif ../tmp-test/out-meta.png


flif.stats: $(FILES_H) $(FILES_CPP) lib/src/flif.cpp
	$(CXX) -std=gnu++11 $(CXXFLAGS) -DSTATS $(OPTIMIZATIONS) -g0 -Wall $(FILES_CPP) flif.cpp $(LDFLAGS) -o flif.stats

flif.prof: $(FILES_H) $(FILES_CPP) lib/src/flif.cpp
	$(CXX) -std=gnu++11 $(CXXFLAGS) $(OPTIMIZATIONS) -g0 -pg -Wall $(FILES_CPP) flif.cpp $(LDFLAGS) -o flif.prof

flif.dbg: $(FILES_H) $(FILES_CPP) lib/src/flif.cpp
	$(CXX) -std=gnu++11 $(CXXFLAGS) -Og -ggdb3 -Wall $(FILES_CPP) flif.cpp $(LDFLAGS) -o flif.dbg

flif.dbg0: $(FILES_H) $(FILES_CPP) lib/src/flif.cpp
	$(CXX) -std=gnu++11 $(CXXFLAGS) -O0 -ggdb3 -Wall $(FILES_CPP) flif.cpp $(LDFLAGS) -o flif.dbg

flif.asan: $(FILES_H) $(FILES_CPP) lib/src/flif.cpp
	$(CXX) -std=gnu++11 $(CXXFLAGS) $(OPTIMIZATIONS) -DDEBUG -fsanitize=address,undefined -fno-omit-frame-pointer -g3 -Wall $(FILES_CPP) flif.cpp $(LDFLAGS) -o flif.asan

viewflif.asan: libflif$(LIBEXT) lib/src/viewflif.c
	$(CC) -std=gnu11 -O0 -ggdb3 -fsanitize=address,undefined $(shell sdl2-config --cflags) -Wall -Ilibrary/ viewflif.c -L. -lflif $(shell sdl2-config --libs) -o viewflif.asan

# make UBSAN print stacktrace
test.asan: export UBSAN_OPTIONS = print_stacktrace=1
test.asan: flif.asan test-interface viewflif.asan
	mkdir -p ../tmp-test
	./test-interface ../tmp-test/dummy.flif
# ASAN may find leaks in code which is not ours and in that case it will throw bad exitcodes on first occurence
# but we want or tests to continue running, so ignore exit code for now
	../tools/test-roundtrip.sh ./flif.asan ../tools/2_webp_ll.png ../tmp-test/2_webp_ll.flif ../tmp-test/decoded_2_webp_ll.png || true
	../tools/test-roundtrip.sh ./flif.asan ../tools/kodim01.png ../tmp-test/kodim01.flif ../tmp-test/decoded_kodim01.png  || true
	../tools/test-lossy.sh ./flif.asan ../tools/kodim01.png ../tmp-test/kodim01-lossy.flif ../tmp-test/decoded_kodim01-lossy.png || true
	../tools/test-roundtrip_anim.sh ./flif.asan ../tools/endless_war.gif ../tmp-test/endless_war.flif || true
	../tools/test-roundtrip_anim_framedir.sh ./flif.asan ../tools/bouncing_ball_frames ../tmp-test/bouncing_ball.flif || true
