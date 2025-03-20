import nifpga
import os

def find_fpga_file(directory, ext=".lvbitx"):
    """
    Search the provided directory for a file with a specific extension.
    Returns the full path of the file if found, or None otherwise.
    """
    search_directory: list = os.listdir(directory)
    for filename in search_directory:
        if (filename == "venv"):
            continue
        current_dir = os.path.join(directory, filename)
        if os.path.isdir(current_dir):
            for discover_dir in os.listdir(current_dir):
                search_directory.append(os.path.join(current_dir, discover_dir))
            print(search_directory)
        elif filename.lower().endswith(ext):
            return os.path.join(directory, filename)
    return "Not Found"

class printer:
    def __init__(self, H, d, K=0.8333, Uz=3.5, address="172.22.11.2"):
        self.H = H/1000 # mm to m
        self.d = d/1000 # mm to m
        self.K = K
        self.Uz = Uz*1000 # kV to V
        self.command = []
        self.address = address
        self.connected = False
        self.session: nifpga.Session = None
        self.calibrationData = []
        self.bindToNiFPGA()
        
    def updateValues(self, H, d, K=0.8333, Uz=3.5):
        self.H = H
        self.d = d
        self.K = K
        self.Uz = Uz
        
    def saveCalibrationData(self, coordinates: list[str], calibrationVoltages: list[list[float]]):
        print(f"Saving calibration data")
        for i in range(0,len(coordinates)):
            coordinate_ux = float(calibrationVoltages[i][0])
            coordinate_uy = float(calibrationVoltages[i][1])
            coordinate_x = float(coordinates[i].split(",")[0])
            coordinate_y = float(coordinates[i].split(",")[1])
            self.calibrationData.append([coordinate_x, coordinate_y, coordinate_ux, coordinate_uy])
        print(f"Calibration data saved")
        print(self.calibrationData)
        
    def bindToNiFPGA(self):
        # Search the FPGA .lvbitx file
        bitfile = find_fpga_file("./", ".lvbitx")
        try:
            self.session = nifpga.Session(bitfile, f"rio://{self.address}/RIO0")
        except Exception as e:
            print(f"Error: {e}")
            return -1
        return 0
            
    
    def verifySession(self):
        self.session.reset()
        self.session.run()
        my_control = self.session.registers['MyConstant']
        my_register = self.session.registers['MyRegister']
        my_control.write(3)
        data = my_register.read()
        if data == 9:
            self.connected = True
            print("Connected to FPGA")
            return 0
        else:
            self.connected = False
            print("Failed to connect to FPGA")
            return -1
        
    
    def updateAddress(self, address):
        self.address = address
        self.closeSession()
        self.bindToNiFPGA()
    
    def clearCommand(self):
        self.command = []
    
    def setUz(self, Uz):
        self.Uz = Uz
        
    def setK(self, K):
        self.K = K
        
    def setH(self, H):
        self.H = H
        
    def setd(self, d):
        self.d = d
    
    def addCommand(self, Ua, Ub, Uc, Ud, type = 0):
        self.command.append([type, Ua/1000, Ub/1000, Uc/1000, Ud/1000])
    
    def toPos(self, Ux = 0, Uy = 0, Ua = 0, Ub = 0, Uc = 0, Ud = 0):
        if Ux == 0 and Uy == 0:
            Ux = self.Uz*(Ua-Uc)
            Uy = self.Uz*(Ub-Ud)
        x = self.K*Ux/self.Uz*(self.H**2)/self.d
        y = self.K*Uy/self.Uz*(self.H**2)/self.d
        return x, y
    
    def toU(self, x, y):
        print(x, y)
        
        Ux = x*self.d/(self.K*self.H**2)*self.Uz
        Uy = y*self.d/(self.K*self.H**2)*self.Uz
        
        # First calculation, assume Ua + Uc = Ub + Ud
        Ua = (1250 + Ux)/2
        Uc = (1250 - Ux)/2
        Ub = (1250 + Uy)/2
        Ud = (1250 - Uy)/2
        
        # If any one of them smaller than zero, adjust algorithm by setting the minimum value to zero
        value = [Ua, Uc, Ub, Ud]
        min_value = min(value)
        if min_value < 0:
            min_index = value.index(min_value)
            if min_index == 0 or min_index == 2:
                Ua = value[0] - min_value
                Uc = value[1] - min_value
                Ub = value[2] + min_value
                Ud = value[3] + min_value
            else:
                Ua = value[0] + min_value
                Uc = value[1] + min_value
                Ub = value[2] - min_value
                Ud = value[3] - min_value
        
        min_value = min(Ua, Uc, Ub, Ud)
        if min_value < 0:
            return Ux, Uy, Ua, Ub, Uc, Ud, -1
        
        
        # Uc = 0
        # Ua = Ux + Uc
        # Ub = (Uy - Ua - Uc + 2500)/2
        # Ud = Ub - Uy
        return Ux, Uy, Ua, Ub, Uc, Ud, 0
    
    def closeSession(self):
        if self.session is not None:
            try:
                self.session.close()
            except Exception as e:
                print(f"Error: {e}")
            finally:
                self.session = None
        print("Session closed")
        return 0
        
    
    def __del__(self):
        self.closeSession()
    
    def executeCommand(self, in_command = []):
        
        if in_command != []:
            print(f"Executing command: {in_command}")
        else:
            for command in self.command:
                print(f"Executing command: {command}")
            
