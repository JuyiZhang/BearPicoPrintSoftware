import time
import nifpga
import os
from FPGA import find_fpga_file


class printer:
    def __init__(self, H, d, K=0.8333, Uz=3.5, address="172.22.11.2"):
        self.H = H/1000 # mm to m
        self.d = d/1000 # mm to m
        self.K = K
        self.Uz = Uz*1000 # kV to V
        self.command = []
        self.fbVoltage = []
        self.address = address
        self.connected = False
        self.session: nifpga.Session = None
        self.calibrationData = []
        self.bindToNiFPGA()
    
    def __deinit__(self):
        if self.session is not None:
            try:
                self.session.close()
            except Exception as e:
                print(f"Error: {e}")
            finally:
                self.session = None
        print("Session closed")
        return 0
    
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
        self.bitfile = find_fpga_file("./", ".lvbitx")
        if self.bitfile == "Not Found":
            print("FPGA file not found")
            return 1
        self.session = nifpga.Session(self.bitfile, f"rio://{self.address}/RIO0")
        self.session.reset()
        self.session.run()
        #     my_control = session.registers['MyConstant']
        #     my_register = session.registers['MyRegister']
        #     my_control.write(3)
        #     data = my_register.read()
        #     print(data)  
    
    def updateFirmware(self, firmware_path):
        if os.path.exists(firmware_path):
            try:
                if self.session is not None:
                    self.session.close()
                self.session = None
                self.bitfile = firmware_path
                self.session = nifpga.Session(self.bitfile, f"rio://{self.address}/RIO0")
                self.session.reset()
                self.session.run()
                print("Firmware updated")
                return 0
            except Exception as e:
                print(f"Error: {e}")
                return 1
        else:
            print(f"Firmware file {firmware_path} not found")
            return 1
     
    def updateVoltage(self, Ua, Ub, Uc, Ud):
        threshold = 20
        if self.session is not None:
            try:
                self.session.registers['Control 1'].write(Ua)
                self.session.registers['Control 2'].write(Ub)
                self.session.registers['Control 3'].write(Uc)
                self.session.registers['Control 4'].write(Ud)
                while True:
                    Uam = self.session.registers['Monitor 1'].read()
                    Ubm = self.session.registers['Monitor 2'].read()
                    Ucm = self.session.registers['Monitor 3'].read()
                    Udm = self.session.registers['Monitor 4'].read()
                    if abs(Uam - Ua) < threshold and abs(Ubm - Ub) < threshold and abs(Ucm - Uc) < threshold and abs(Udm - Ud) < threshold:
                        print(f"Voltage updated: {Ua}, {Ub}, {Uc}, {Ud}")
                        self.fbVoltage.append([Uam, Ubm, Ucm, Udm])
                        return 0, Uam, Ubm, Ucm, Udm
            except Exception as e:
                print(f"Error: {e}")
                return 1, 0, 0, 0, 0
        else:
            print("Session is not connected")
            return 1, 0, 0, 0, 0
    
    def dispense(self):
        if self.session is not None:
            try:
                self.session.registers['Dispense Indicator'].write(True)
                time.sleep(0.01)
                self.session.registers['Dispense Indicator'].write(False)
                time.sleep(0.01)
                print("Dispense command executed")
                return 0
            except Exception as e:
                print(f"Error: {e}")
                return 1
        else:
            print("Session is not connected")
            return 1
    
    def beginPrint(self):
        if self.session is not None:
            try:
                self.session.registers['HV Enable'].write(True)
                print("HV Enable command executed")
                for command in self.command:
                    if self.updateVoltage(command[1], command[2], command[3], command[4]) == 0:
                        if self.dispense() == 0:
                            print("Dispense command executed")
                        else:
                            print("Error dispensing")
                            return 1
                    else:
                        print("Error updating voltage")
                        return 1
                self.session.registers['HV Enable'].write(False)
                print("Print Finish, Enjoy!")
                return 0
            except Exception as e:
                print(f"Error: {e}")
                return 1
        else:
            print("Session is not connected")
            return 1
    
    def clearfbVoltage(self):
        self.fbVoltage = []
    
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
            
