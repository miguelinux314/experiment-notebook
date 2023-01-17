.. Image manipulation (with isets.py)

.. include:: ./tag_definition.rst

Image manipulation
==================

The `enb` library provides tools to work with image files. 

Special focus has been placed to simplify the **loading and saving of raw BSQ images**.
In memory, `numpy` is employed, which makes it easy to interface with other libraries.

The image manipulation tools in `enb` can be useful when defining your own `enb` experiments, 
but also as standalone functions. 

Raw format
>>>>>>>>>>

When in disk, images are assumed to be stored in **raw (uncompressed, BSQ) format**, meaning:

* Each pixel is stored with a constant number of bytes per sample (1, 2, 4 or 8, typically)
* BSQ order is assumed, *i.e.*, pixels of each spectral band are sequentially stored in raster order (row by row, left to right).

When storing an image in raw format, its geometry (width, height, number of spectral components) 
and data type (bytes per sample, endianness, integer/float)
need to be known.  

The `.raw` file format is often assumed.

Read raw images: enb.isets.load_array_bsq
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

The :func:`enb.isets.load_array_bsq` function allows you to load raw images from disk.
To specify the geometry and data type of the file, you need to use at least one of the following:

* Pass the `width`, `height`, `component_count`, `dtype` (numpy format) parameters to `load_array_bsq`, *e.g.*,

  .. code-block:: python

     im = enb.isets.load_array_bsq("img.raw", dtype=">u4", width=2078, height=2136, component_count=1) 


* Pass the `image_properties_row` parameter (a dictionary with the above keys) to `load_array_bsq`, *e.g.*, 
    
  .. code-block:: python 

    image_properties_row = dict(dtype=">u4", width=2078, height=2136, component_count=1)
    im = enb.isets.load_array_bsq("img.raw", image_properties_row=image_properties_row)

* Use **name tags** when choosing filenames for images in raw format.
  These tags, *e.g.,* `u8be-3x600x800` inform `enb` of all the required geometry.
  The format of these tags (which can appear anywhere in the filename) is:

     - `u` or `s` for unsigned and signed, respectively
     - the number of bits per sample (typically, 8, 16, 32 or 64)
     - `be` or `le` for big-endian and little-endian formats, respectively
     - `ZxYxX`, where `Z` is the number of spectral compoments (3 in the example),
       `X` the width (number of columns, 800 in the example)
       and `Y` the height (number of rows, 600 in the example).

  When name tags are employed, only the file path parameter is required by `load_array_bsq`, *e.g.,*

  .. code-block:: python

    im = enb.isets.load_array_bsq("img-u32be-1x2136x2078.raw")


Images are numpy arrays
>>>>>>>>>>>>>>>>>>>>>>>

The `enb` library uses `numpy` whenever possible.

The return of `enb.isets.load_array_bsq` is a 3-D numpy array with the image data, which can be indexed as [x,y,z].

You can use all of numpys functionality directly on these arrays, 
including efficient `slicing <https://www.w3schools.com/python/numpy/numpy_array_slicing.asp>`_,
`arithmetic operations <https://scipy-lectures.org/intro/numpy/operations.html>`_
and its use in many other libraries such as `scipy <https://scipy.org/>`_ and `pandas <https://pandas.pydata.org/>`_.  

.. note:: The index order of the returned image ((x,y,z), "F") differs from the default assumed 
          by numpy's functions ((z,y,x), "C").

Saving images to disk: enb.isets.dump_array_bsq
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

If you have a 3D numpy array indexed by [x,y,z], you can store it in BSQ raw format with
the :func:`enb.isets.dump_array_bsq` method, *e.g.*, 

.. code-block:: python

    im = enb.isets.load_array_bsq("img-u32be-1x2136x2078.raw")
    enb.isets.dump_array_bsq(im, "copy_of_img-u32be-1x2136x2078.raw")
          
By default, the output geometry and data type are derived from the numpy array type.
If you loaded the array with `enb.isets.load_array_bsq` and didn't modify it,
`enb.isets.dump_array_bsq` stores an identical copy of the original.

If needed, you can pass the `dtype` argument (numpy format) to `dump_array_bsq` 
and. In this case:

    1. The array is casted to `dtype` (it is up to the user to check it is a safe cast)
    2. The raw file format is derived from the chosen value of `dtype`, *e.g.,*,
       `>u2` for 16-bit unsigned big-endian integers, and `<i4` for 32-bit signed little-endian integers. 

Appendix: function interfaces
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

.. autofunction:: enb.isets.load_array_bsq
.. autofunction:: enb.isets.dump_array_bsq