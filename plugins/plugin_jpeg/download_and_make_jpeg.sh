#!/bin/bash

mkdir tmp
cd tmp
wget https://github.com/thorfdbg/libjpeg/archive/master.zip
unzip master.zip
cd libjpeg-master/
./configure
make
cp jpeg ../../
cd ../../
rm -rf tmp
