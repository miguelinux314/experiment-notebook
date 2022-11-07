import enb.plugins


class HDF5Plugin(enb.plugins.Plugin):
    name = "hdf5"
    label = "Codec wrappers for the h5py library"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Andrew Collete et al."]
    contrib_reference_urls = ["https://github.com/h5py/h5py"]
    required_pip_modules = ["h5py"]
    tested_on = {"linux"}
