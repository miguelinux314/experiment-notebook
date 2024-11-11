import os
import stat
import subprocess
import zipfile
import shutil

import enb.plugins


class TRPXPlugin(enb.plugins.Plugin):
    target_ref = "master"
    
    name = "trpx"
    label = "trpx (Terse/Prolix) codec"
    tags = {"data compression", "codec"}
    contrib_authors = ["Senik Matinyan"]
    contrib_reference_urls = ["https://github.com/senikm/trpx"]
    contrib_download_url_name = [
        (f"https://github.com/miguelinux314/trpx/archive/refs/heads/{target_ref}.zip",
         "trpx_codec_src.zip")]
    tested_on = {"linux"}

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False):
        # Check that required tools are present before installing
        for binary in ("make", "cmake"):
            if shutil.which(binary) is None:
                raise ValueError(f"{binary} is not installed but it is need to install {cls.name} ({cls.label})")
            
        # Peform installation
        super().install(installation_dir=installation_dir, overwrite_destination=overwrite_destination)

    @classmethod
    def build(cls, installation_dir):
        # Copy files
        super().build(installation_dir=installation_dir)

        # Decompress the codec source
        assert len(cls.contrib_download_url_name) == 1
        with zipfile.ZipFile(os.path.join(installation_dir, cls.contrib_download_url_name[0][1])) as zfile:
            zfile.extractall(installation_dir)

        # Generate binaries (requires cmake and make)
        cwd = os.getcwd()
        try:
            src_dir = os.path.join(installation_dir, f"trpx-{cls.target_ref}")
            os.chdir(src_dir)

            # Generate build files
            invocation = f"cmake ."
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\nInput=[{invocation}].\nOutput=[{output}]")

            # Compile
            invocation = "cmake --build ."
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\nInput=[{invocation}].\nOutput=[{output}]")
            
            # Copy binary and make executable
            binary_path = os.path.join(installation_dir, "raw_codec") 
            shutil.copyfile(os.path.join(src_dir, "src", "raw_codec"), binary_path)
            os.chmod(binary_path, os.stat(binary_path).st_mode | stat.S_IEXEC)
            
        finally:
            os.chdir(cwd)
