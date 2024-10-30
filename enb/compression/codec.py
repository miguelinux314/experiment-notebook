"""Codecs implement the `compress` and `decompress` methods
as well as a `name` and `label` to identify and represent them.

A `param_dict` is passed on initialization that describes the configuration of each codec instance.
Codecs may choose the number of parameters and their names.  
"""
import shutil
from enb.experiment import ExperimentTask
from enb.compression import CompressionResults, DecompressionResults

class AbstractCodec(ExperimentTask):
    """Base class for all codecs.
    """

    def __init__(self, param_dict=None):
        """
        :param param_dict: dictionary of parameters for this codec instance.
        """
        super().__init__(param_dict=param_dict)

    @property
    def name(self):
        """Name of the codec. Subclasses are expected to yield different
        values when different parameters are used. By default, the class name
        is folled by all elements in self.param_dict sorted alphabetically
        are included in the name.
        """
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(
                f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        """Label to be displayed for the codec. May not be strictly unique
        nor fully informative. By default, self's class name is returned.
        """
        return self.__class__.__name__

    def compress(self, original_path: str, compressed_path: str, original_file_info=None) -> CompressionResults:
        """Compress original_path into compress_path using param_dict as params.
        :param original_path: path to the original file to be compressed
        :param compressed_path: path to the compressed file to be created
        :param original_file_info: a dict-like object describing
          original_path's properties (e.g., geometry), or None.
        :return: (optional) a CompressionResults instance, or None
          (see self.compression_results_from_paths)
        """
        raise NotImplementedError()

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).

        :param compressed_path: path to the input compressed file
        :param reconstructed_path: path to the output reconstructed file
        :param original_file_info: a dict-like object describing
          original_path's properties (e.g., geometry), or None. Should only be
          actually used in special cases, since codecs are expected to store
          all needed metainformation in the compressed file.
        :return: (optional) a DecompressionResults instance, or None (see
        self.decompression_results_from_paths)
        """
        raise NotImplementedError()

    def compression_results_from_paths(self, original_path, compressed_path):
        """Get the default CompressionResults instance corresponding to
        the compression of original_path into compressed_path
        """
        return CompressionResults(
            codec_name=self.name,
            codec_param_dict=self.param_dict,
            original_path=original_path,
            compressed_path=compressed_path,
            compression_time_seconds=None)

    def decompression_results_from_paths(
            self, compressed_path, reconstructed_path):
        """Return a enb.icompression.DecompressionResults instance given
        the compressed and reconstructed paths.
        """
        return DecompressionResults(
            codec_name=self.name,
            codec_param_dict=self.param_dict,
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            decompression_time_seconds=None)

    def __repr__(self):
        return f"<{self.__class__.__name__}(" \
            + ', '.join(repr(param) + '=' + repr(value)
                        for param, value in self.param_dict.items()) \
            + ")>"

class LosslessCodec(AbstractCodec):  # pylint: disable=abstract-method
    """An AbstractCodec that identifies itself as lossless.
    """


class LossyCodec(AbstractCodec):  # pylint: disable=abstract-method
    """An AbstractCodec that identifies itself as lossy.
    """


class NearLosslessCodec(LossyCodec):  # pylint: disable=abstract-method
    """An AbstractCodec that identifies itself as near lossless.
    """
    
class PassthroughCodec(LosslessCodec):
    """Codec that simply copies the input into the output in both compression and decompression.
    """
    def __init__(self):
        super().__init__()
    
    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        shutil.copyfile(original_path, compressed_path)
        
    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        shutil.copyfile(compressed_path, reconstructed_path)