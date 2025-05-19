import time
import nifpga
import os
import tkinter as tk
from tkinter import ttk
from FPGA import find_fpga_file


class printer:
    def __init__(self, H, d, K=0.8333, Uz=3.5, address="172.22.11.2"):
        self.H = H/1000 # mm to m
        self.d = d/1000 # mm to m
        self.K = K
        self.dispenseInterval = 0.1 # seconds
        self.vthreshold = 0.1 # ratio
        self.Uz = Uz*1000 # kV to V
        self.command = []
        self.fbVoltage = []
        self.voltageCalibrationA = []
        self.voltageCalibrationB = []
        self.voltageCalibrationC = []
        self.voltageCalibrationD = []
        self.calibrationType = 'N' # N: No calibration, V: Voltage calibration, C: Coordinate calibration, B: Both calibration
        self.address = address
        self.connected = False
        self.session: nifpga.Session = None
        self.coordinateCalibrationData = []
        self.bindToNiFPGA()
    
    def setEnableCalibration(self, calibration_type):
        if calibration_type not in ['N', 'V', 'C', 'B']:
            print("Invalid calibration type. Use 'N' for No calibration, 'V' for Voltage calibration, 'C' for Coordinate calibration, 'B' for Both calibration.")
            return 1
        if self.coordinateCalibrationData == [] and (calibration_type == 'C' or calibration_type == 'B'):
            print("No coordinate calibration data found. Please perform coordinate calibration first.")
            self.calibrationType = 'N'
            return 1
        self.calibrationType = calibration_type
        print(f"Calibration type set to {calibration_type}")
        return 0
    
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
        filename = 'coordinateCalibration.cal'
        with open(filename, 'w') as f:
            f.write("Coordinate Calibration Data\n")
            for i in range(len(self.calibrationData)):
                f.write(f"{self.calibrationData[i][0]} {self.calibrationData[i][1]} {self.calibrationData[i][2]} {self.calibrationData[i][3]}\n")
        print(f"Coordinate calibration data saved to {filename}")
        return 0
    
    def loadCalibrationData(self):
        filename = 'coordinateCalibration.cal'
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if "Coordinate" in line:
                        continue
                    coordinate_x = float(line.split()[0])
                    coordinate_y = float(line.split()[1])
                    coordinate_ux = float(line.split()[2])
                    coordinate_uy = float(line.split()[3])
                    self.coordinateCalibrationData.append([coordinate_x, coordinate_y, coordinate_ux, coordinate_uy])
            print(f"Coordinate calibration data loaded from {filename}")
        else:
            print(f"Coordinate calibration data file {filename} not found")
            return 1
        return 0
        
    def bindToNiFPGA(self):
        # Search the FPGA .lvbitx file
        self.bitfile = find_fpga_file("./", ".lvbitx")
        if self.bitfile == "Not Found":
            print("FPGA file not found")
            return 1
        
        print(f"FPGA file found: {self.bitfile}")
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
                print("Firmware updated to ", firmware_path)
                return 0
            except Exception as e:
                print(f"Error: {e}")
                return 1
        else:
            print(f"Firmware file {firmware_path} not found")
            return 1
     
    def updateVoltage(self, Ua, Ub, Uc, Ud):
        threshold_min = 100
        
        if self.session is not None:
            try:
                self.session.registers['Control 1'].write(Ua)
                self.session.registers['Control 2'].write(Ub)
                self.session.registers['Control 3'].write(Uc)
                self.session.registers['Control 4'].write(Ud)
                current_time = time.time()
                while True:
                    Uam = float(self.session.registers['Monitor 1'].read())*5000
                    Ubm = float(self.session.registers['Monitor 2'].read())*5000
                    Ucm = float(self.session.registers['Monitor 3'].read())*5000
                    Udm = float(self.session.registers['Monitor 4'].read())*5000
                    if time.time() - current_time > 0.5:
                        print("Timeout waiting for voltage update")
                        print(f"Voltage: {Uam}, {Ubm}, {Ucm}, {Udm}")
                        return 1, 0, 0, 0, 0
                    threshold = max(max(Uam, Ubm, Ucm, Udm) * self.vthreshold, threshold_min)
                    if abs(Uam - Ua) < threshold and abs(Ubm - Ub) < threshold and abs(Ucm - Uc) < threshold and abs(Udm - Ud) < threshold:
                        print(f"Voltage updated: {Ua}, {Ub}, {Uc}, {Ud}")
                        self.fbVoltage.append([Uam, Ubm, Ucm, Udm])
                        return 0, Uam, Ubm, Ucm, Udm
            except Exception as e:
                print(f"Error during update voltage: {e}")
                return 1, 0, 0, 0, 0
        else:
            print("Session is not connected")
            return 1, 0, 0, 0, 0
    
    def dispense(self):
        if self.session is not None:
            try:
                self.session.registers['Dispense Indicator'].write(True)
                time.sleep(self.dispenseInterval/2)
                self.session.registers['Dispense Indicator'].write(False)
                time.sleep(self.dispenseInterval/2)
                print("Dispense command executed")
                return 0
            except Exception as e:
                print(f"Error during dispense: {e}")
                return 1
        else:
            print("Session is not connected")
            return 1
    
    def calibrateVoltage(self, vin, channel):
        if channel == 0:
            voltageCalibration = self.voltageCalibrationA
        elif channel == 1:
            voltageCalibration = self.voltageCalibrationB
        elif channel == 2:
            voltageCalibration = self.voltageCalibrationC
        elif channel == 3:
            voltageCalibration = self.voltageCalibrationD
        else:
            print("Invalid channel")
            return 1
        min_diff = 1000000
        max_diff = 1000000
        min_index = -1
        max_index = -1
        for j in range(len(voltageCalibration)):
            if voltageCalibration[j][1] == vin:
                print("Exact match found")
                return voltageCalibration[j][1]
            diff = abs(voltageCalibration[j][1] - vin)
            diff_sign = True if voltageCalibration[j][1] > vin else False
            if diff_sign and diff < min_diff:
                min_diff = diff
                lower_val = voltageCalibration[j][1]
                min_index = j
            if not diff_sign and diff < max_diff:
                max_diff = diff
                upper_val = voltageCalibration[j][1]
                max_index = j
            if min_index == -1 and max_index == -1:
                min_index = 0
                max_index = 0
        if min_index == -1 or max_index == -1 or min_index == max_index:
            print("Warning: No voltage calibration data found")
            return vin
        print(f"Lower value: {lower_val}, Upper value: {upper_val}, Perform Linear Interpolation to get estimated value")
        linint_slope = (upper_val - lower_val)/(voltageCalibration[j][0] - voltageCalibration[j][0])
        return lower_val + linint_slope*(vin - voltageCalibration[j][0])
    
    def updateCalibrationVoltage(self, channel, inputval, trueval):
        if channel == 0:
            voltageCalibration = self.voltageCalibrationA
        elif channel == 1:
            voltageCalibration = self.voltageCalibrationB
        elif channel == 2:
            voltageCalibration = self.voltageCalibrationC
        elif channel == 3:
            voltageCalibration = self.voltageCalibrationD
        else:
            print("Invalid channel")
            return 1
        valueToRemove = []
        for i in range(len(voltageCalibration)):
            if voltageCalibration[i][0] == inputval:
                valueToRemove = voltageCalibration[i]
        if channel == 0:
            self.voltageCalibrationA.remove(valueToRemove)
            self.voltageCalibrationA.append([inputval, trueval])
        elif channel == 1:
            self.voltageCalibrationB.remove(valueToRemove)
            self.voltageCalibrationB.append([inputval, trueval])
        elif channel == 2:
            self.voltageCalibrationC.remove(valueToRemove)
            self.voltageCalibrationC.append([inputval, trueval])
        elif channel == 3:
            self.voltageCalibrationD.remove(valueToRemove)
            self.voltageCalibrationD.append([inputval, trueval])
        else:
            print("Invalid channel")
            return 1
        print(f"Calibration voltage updated for channel {channel}: {inputval} -> {trueval}")
        return 0
    
    def beginPrint(self, progressbar:ttk.Progressbar = None, outputbox:tk.Text = None):
        if self.session is not None:
            try:
                self.session.registers['HV Enable'].write(True)
                print("HV Enable command executed")
                for i in range(len(self.command)):
                    command = self.command[i]
                    if progressbar is not None:
                        progressbar['value'] = (i+1)/len(self.command)*100
                        progressbar.update()
                    
                    if self.calibrationType == 'V' or self.calibrationType == 'B':
                        for i in range(4):
                            # Find the closest two voltage values in voltageCalibration List
                            command[i] = self.calibrateVoltage(command[i], i)
                    
                    if outputbox is not None:
                        execute_ts = time.time()
                        outputbox.insert("end", f"EXEC {command} {execute_ts}\n")
                        outputbox.see("end")
                        
                    update_rtn, Uam, Ubm, Ucm, Udm = self.updateVoltage(command[1], command[2], command[3], command[4])
                    
                    if self.calibrationType == 'V' or self.calibrationType == 'B':
                        self.updateCalibrationVoltage(0, command[1], Uam)
                        self.updateCalibrationVoltage(1, command[2], Ubm)
                        self.updateCalibrationVoltage(2, command[3], Ucm)
                        self.updateCalibrationVoltage(3, command[4], Udm)
                    
                    if outputbox is not None:
                        execute_ts = time.time()
                        outputbox.insert("end", f"MONI VOLT {Uam} {Ubm} {Ucm} {Udm} {execute_ts}\n")
                        outputbox.see("end")
                    if update_rtn == 0:
                        if outputbox is not None:
                            execute_ts = time.time()
                            outputbox.insert("end", f"DISP BEGI {execute_ts}\n")
                            outputbox.see("end")
                        if self.dispense() == 0:
                            if outputbox is not None:
                                execute_ts = time.time()
                                outputbox.insert("end", f"DISP OKAY {execute_ts}\n")
                                outputbox.see("end")
                            print("Dispense command executed")
                        else:
                            if outputbox is not None:
                                execute_ts = time.time()
                                outputbox.insert("end", f"DISP ERRO {execute_ts}\n")
                                outputbox.see("end")
                            print("Error dispensing")
                            return 1
                    else:
                        if outputbox is not None:
                            execute_ts = time.time()
                            outputbox.insert("end", f"MONI ERRO {execute_ts}\n")
                            outputbox.see("end")
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
        self.command.append([type, Ua, Ub, Uc, Ud])
    
    def toPos(self, Ux = 0, Uy = 0, Ua = 0, Ub = 0, Uc = 0, Ud = 0):
        if Ux == 0 and Uy == 0:
            Ux = self.Uz*(Ua-Uc)
            Uy = self.Uz*(Ub-Ud)
        x = self.K*Ux/self.Uz*(self.H**2)/self.d
        y = self.K*Uy/self.Uz*(self.H**2)/self.d
        return x, y
    
    def toU4(self, Ux, Uy):
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
        
        return Ux, Uy, Ua, Ub, Uc, Ud, 0
    
    def toUCoordCalibrated(self, x, y):
        if self.coordinateCalibrationData == []:
            print("No coordinate calibration data found")
            return 0, 0, 0, 0, 0, 0, 1
        # find the closest four points in the coordinateCalibrationData
        # and perform uvmapping to get the voltage values
        distance_array = []
        for i in range(len(self.coordinateCalibrationData)):
            distance = ((x - self.coordinateCalibrationData[i][0])**2 + (y - self.coordinateCalibrationData[i][1])**2)**0.5
            distance_array.append(distance)
        # get the index of the four closest points
        index_array = sorted(range(len(distance_array)), key=lambda i: distance_array[i])[:4]
        # get the four closest points
        closest_points = [self.coordinateCalibrationData[i] for i in index_array]
        # get the voltage values of the four closest points
        closest_voltages = [self.coordinateCalibrationData[i][2:4] for i in index_array]
        # perform bilinear interpolation to get the voltage values
        x1 = closest_points[0][0]
        y1 = closest_points[0][1]
        x2 = closest_points[1][0]
        y2 = closest_points[1][1]
        x3 = closest_points[2][0]
        y3 = closest_points[2][1]
        x4 = closest_points[3][0]
        y4 = closest_points[3][1]
        ux1 = closest_points[0][2]
        uy1 = closest_points[0][3]
        ux2 = closest_points[1][2]
        uy2 = closest_points[1][3]
        ux3 = closest_points[2][2]
        uy3 = closest_points[2][3]
        ux4 = closest_points[3][2]
        uy4 = closest_points[3][3]
        # solve for uv coordinate in x and y
        u = (ux1*(x2-x)/(x2-x1) + ux2*(x-x1)/(x2-x1) + ux3*(x4-x)/(x4-x3) + ux4*(x-x3)/(x4-x3)) / ((y2-y1)*(x2-x1) + (y4-y3)*(x4-x3))
        v = (uy1*(y2-y)/(y2-y1) + uy2*(y-y1)/(y2-y1) + uy3*(y4-y)/(y4-y3) + uy4*(y-y3)/(y4-y3)) / ((x2-x1)*(y2-y1) + (x4-x3)*(y4-y3))
        # get the voltage values from uv
        ux = (1-u)*(1-v)*ux1 + u*(1-v)*ux2 + (1-u)*v*ux3 + u*v*ux4
        uy = (1-u)*(1-v)*uy1 + u*(1-v)*uy2 + (1-u)*v*uy3 + u*v*uy4
        # check if the voltage values are in the range of 0 to 5000
        if ux < 0 or ux > 5000 or uy < 0 or uy > 5000:
            print("Voltage values out of range")
        # return the voltage values
        return self.toU4(ux, uy)
    
    def toU(self, x, y):
        print(x, y)
        
        Ux = x*self.d/(self.K*self.H**2)*self.Uz
        Uy = y*self.d/(self.K*self.H**2)*self.Uz
        
        return self.toU4(Ux, Uy)
    
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
        
    def saveVCalibrationData(self):
        filename = 'voltageCalibration.cal'
        with open(filename, 'w') as f:
            f.write("Voltage Calibration Data\n")
            f.write("Channel 1\n")
            for i in range(len(self.voltageCalibrationA)):
                f.write(f"{self.voltageCalibrationA[i][0]} {self.voltageCalibrationA[i][1]}\n")
            f.write("Channel 2\n")
            for i in range(len(self.voltageCalibrationB)):
                f.write(f"{self.voltageCalibrationB[i][0]} {self.voltageCalibrationB[i][1]}\n")
            f.write("Channel 3\n")
            for i in range(len(self.voltageCalibrationC)):
                f.write(f"{self.voltageCalibrationC[i][0]} {self.voltageCalibrationC[i][1]}\n")
            f.write("Channel 4\n")
            for i in range(len(self.voltageCalibrationD)):
                f.write(f"{self.voltageCalibrationD[i][0]} {self.voltageCalibrationD[i][1]}\n")
        print(f"Voltage calibration data saved to {filename}")
    
    def loadVCalibrationData(self):
        filename = 'voltageCalibration.cal'
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                lines = f.readlines()
                channel = -1
                for line in lines:
                    if "Channel" in line:
                        channel += 1
                        continue
                    if channel == 0:
                        self.voltageCalibrationA.append([float(line.split()[0]), float(line.split()[1])])
                    elif channel == 1:
                        self.voltageCalibrationB.append([float(line.split()[0]), float(line.split()[1])])
                    elif channel == 2:
                        self.voltageCalibrationC.append([float(line.split()[0]), float(line.split()[1])])
                    elif channel == 3:
                        self.voltageCalibrationD.append([float(line.split()[0]), float(line.split()[1])])
            print(f"Voltage calibration data loaded from {filename}")
        else:
            print(f"Voltage calibration data file {filename} not found")
            return 1
        return 0
    
    def __del__(self):
        
        self.closeSession()
    
    def executeCommand(self, in_command = [], progressbar = None, outputbox = None):
        
        if in_command != []:
            self.command = in_command
        self.beginPrint()
            
