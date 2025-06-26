"""enb.compression: data compression in enb.

The compression and icompression modules implement enb.experiment.Experiment classes 
and other basic tools to facilitate them.

Several other modules are declared for specific compressed data formats.
"""

from .compression import *
from . import codec
from . import icompression
from . import wrapper

from . import tarlite
from . import fits
from . import jpg
from . import pgm
from . import png
