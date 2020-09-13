import pkgutil as _pkgutil

import enb.icompression

# Dynamically updated by inspection of modules found
__all__ = []
all_codec_classes = []
all_lossless_codec_classes = []
all_lossy_codec_classes = []

for loader, module_name, is_pkg in _pkgutil.walk_packages(__path__):
    if not module_name.startswith("codec"):
        continue
    __all__.append(module_name)
    _module = loader.find_module(module_name).load_module(module_name)
    for _element in dir(_module):
        if not isinstance(_element, str):
            continue
        cls = getattr(_module, _element)
        if not type(cls) == type:
            continue
        if issubclass(cls, enb.icompression.AbstractCodec):
            all_codec_classes.append(cls)
        if issubclass(cls, enb.icompression.LosslessCodec):
            all_lossless_codec_classes.append(cls)
        if issubclass(cls, enb.icompression.LossyCodec):
            all_lossy_codec_classes.append(cls)
