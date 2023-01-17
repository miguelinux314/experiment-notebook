#!/bin/bash
# Serve the local version of the documentation and open it in firefox.

php -S localhost:9999 -t $(pwd -P)/build/html &

firefox localhost:9999

