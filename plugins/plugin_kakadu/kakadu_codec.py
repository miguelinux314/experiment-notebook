import os
import tempfile
from enb import icompression
from enb.config import get_options
from enb import tcall

options = get_options()

class Kakadu(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self, HT=False, Clevels=5):
        assert isinstance(HT, bool), "HT must be a boolean (True/False)"
        assert Clevels in range(0,33), "Clevels should be an integer between 0 and 33"
        
        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "kdu_compress"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "kdu_expand"),
            param_dict={'HT':HT,'Clevels':Clevels}, output_invocation_dir=None)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path}*{original_file_info['component_count']}@{original_file_info['width']*original_file_info['height']*original_file_info['bytes_per_sample']}" \
               f" -o {compressed_path} -no_info -full -no_weights Corder=LRCP Clevels={self.param_dict['Clevels']} Clayers={original_file_info['component_count']} Creversible=yes Cycc=no " \
               f"Sdims=\\{{{original_file_info['width']},{original_file_info['height']}\\}} Nprecision={original_file_info['bytes_per_sample']*8} " \
               f"Nsigned={'yes' if original_file_info['signed'] else 'no'} {'Cmodes=HT' if self.param_dict['HT']==True else ''}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i {compressed_path} -o {reconstructed_path} -raw_components"

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        compression_params = self.get_compression_params(
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info)
        invocation = f"{self.compressor_path} {compression_params}"
        try:
            status, output, measured_time = tcall.get_status_output_time(invocation=invocation)
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            raise CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        compression_results = self.compression_results_from_paths(
            original_path=original_path, compressed_path=compressed_path)
        compression_results.compression_time_seconds = measured_time

        if self.output_invocation_dir is not None:
            invocation_name = "invocation_compression_" \
                              + self.name \
                              + os.path.abspath(os.path.realpath(original_file_info["file_path"])).replace(os.sep, "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
                invocation_file.write(f"Original path: {original_path}\n"
                                      f"Compressed path: {compressed_path}\n"
                                      f"Codec: {self.name}\n"
                                      f"Invocation: {invocation}\n"
                                      f"Status: {status}\n"
                                      f"Output: {output}\n"
                                      f"Measured time: {measured_time}")

        return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        temp_list = []
        temp_path = f""
        for i in range(0, original_file_info['component_count']):
            temp_list.append(tempfile.NamedTemporaryFile(suffix=".raw").name)
            if i < (original_file_info['component_count'] - 1):
                temp_path += f"{temp_list[i]},"
            else:
                temp_path += f"{temp_list[i]}"
        decompression_params = self.get_decompression_params(
            compressed_path=compressed_path,
            reconstructed_path=temp_path,
            original_file_info=original_file_info)
        invocation = f"{self.decompressor_path} {decompression_params}"
        try:
            status, output, measured_time = tcall.get_status_output_time(invocation)
            with open(reconstructed_path, 'wb') as reconstructed:
                for name in temp_path.split(","):
                    with open(name, 'rb') as file:
                        data = file.read()
                        reconstructed.write(data)
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            raise DecompressionException(
                compressed_path=compressed_path,
                reconstructed_path=reconstructed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        decompression_results = self.decompression_results_from_paths(
            compressed_path=compressed_path, reconstructed_path=reconstructed_path)

        decompression_results.decompression_time_seconds = measured_time

        if self.output_invocation_dir is not None:
            invocation_name = "invocation_decompression_" \
                              + self.name \
                              + os.path.abspath(os.path.realpath(
                original_file_info["file_path"] if original_file_info is not None else compressed_path)).replace(os.sep,
                                                                                                                 "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
                invocation_file.write(f"Compressed path: {compressed_path}\n"
                                      f"Reconstructed path: {reconstructed_path}\n"
                                      f"Codec: {self.name}\n"
                                      f"Invocation: {invocation}\n"
                                      f"Status: {status}\n"
                                      f"Output: {output}\n"
                                      f"Measured time: {measured_time}")

        return decompression_results

    @property
    def label(self):
        return "Kakadu" 
    
class Kakadu_MCT(Kakadu):
    def __init__(self, HT=False, Clevels=5):
        Kakadu.__init__(self, HT=HT, Clevels=Clevels)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path}*{original_file_info['component_count']}@{original_file_info['width'] * original_file_info['height'] * original_file_info['bytes_per_sample']} " \
               f"-o {compressed_path} -no_info -full -no_weights Corder=LRCP Clevels={self.param_dic['Clevels']} Clayers={original_file_info['component_count']} " \
               f"Creversible=yes Cycc=no Sdims=\\{{{original_file_info['width']},{original_file_info['height']}\\}} Nprecision={original_file_info['bytes_per_sample'] * 8} " \
               f"Nsigned={'yes' if original_file_info['signed'] else 'no'} Sprecision={original_file_info['bytes_per_sample'] * 8} " \
               f"Ssigned={'yes' if original_file_info['signed'] else 'no'} Mcomponents={original_file_info['component_count']} " \
               f"Mstage_inputs:I1=\\{{0,{original_file_info['component_count']-1}\\}} Mstage_outputs:I1=\\{{0,{original_file_info['component_count']-1}\\}} Mstage_collections:I1=\\{{{original_file_info['component_count']},{original_file_info['component_count']}\\}} " \
               f"Mstage_xforms:I1=\\{{DWT,1,4,0,0\\}} Mvector_size:I4={original_file_info['component_count']} Mvector_coeffs:I4=0 Mnum_stages=1 Mstages=1 {'Cmodes=HT' if self.param_dic['HT'] == True else ''}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i {compressed_path} -o {reconstructed_path} -raw_components"

    @property
    def label(self):
        return "Kakadu_MCT"
