#!/bin/bash

# Run make under every plugin_* dir found in this folder

find -name 'build_errors.log' -exec rm {} \;

for d in plugin_*; do
  cd $d
  echo "Preparing $d ..." | tee -a ./build_errors.log
  test -e Makefile && make clean >& /dev/null
  test -e Makefile && ( (make >& ./build_errors.log) || echo "Error building plugin at $d. See ./build_errors.log for more information" )
  echo "... finished with $d!" | tee -a ./build_errors.log
  echo "" | tee -a ./build_errors.log
  cd ..
done
