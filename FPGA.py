import nifpga
import os
import numpy as np
from nifpga.session import _ArrayRegister 

def find_fpga_file(directory, ext=".lvbitx"):
    """
    Search the provided directory for a file with a specific extension.
    Returns the full path of the file if found, or None otherwise.
    """
    search_directory: list = os.listdir(directory)
    for filename in search_directory:
        current_dir = os.path.join(directory, filename)
        if os.path.isdir(current_dir):
            for discover_dir in os.listdir(current_dir):
                search_directory.append(os.path.join(current_dir, discover_dir))
            print(search_directory)
        elif filename.lower().endswith(ext):
            return os.path.join(directory, filename)
    return "Not Found"

class FPGA:
    def __init__(self):
        self.bitfile = find_fpga_file("./", ".lvbitx")
        with nifpga.Session(self.bitfile, "rio://172.22.11.2/RIO0") as session:
            session.reset()
            session.run()
            print(session.registers)
            array_register: _ArrayRegister = session.registers['array']
            array_to_write = np.zeros(64)
            print(array_to_write)
            array_register.write(array_to_write)
            print(array_register.read())
            array_to_write = np.ones(64)
            array_to_write[50] = 3.10024345
            array_register.write(array_to_write)
            print(array_register.read())
            array_count = session.registers['Numeric']
            print(array_count.read())
            
            
if __name__ == "__main__":
    fpga = FPGA()