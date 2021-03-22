#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import with_statement, print_function
import sys, os
import tempfile
import warnings
from numpy import arange, array
from pkg_resources import resource_filename
import fitsio
from fitsio import FITS, FITSHDR
#from ._fitsio_wrap import cfitsio_use_standard_strings

import unittest
from math import floor, ceil
from typing import AnyStr
#from astropy.io import fits
import numpy as np
import gzip
import shutil 
import self




filename='./CALIFAIC0159.V500.rscube.fits' #FLOAT
data= fitsio.read(filename)
fitsio.write('CAL_g.fit', data, compress='gzip', qlevel=None)
