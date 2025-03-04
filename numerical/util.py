import nifpga

class printer:
    def __init__(self, H, d, K=0.8333, Uz=3.5):
        self.H = H/1000 # mm to m
        self.d = d/1000 # mm to m
        self.K = K
        self.Uz = Uz*1000 # kV to V
        self.command = []
        
    def updateValues(self, H, d, K=0.8333, Uz=3.5):
        self.H = H
        self.d = d
        self.K = K
        self.Uz = Uz
    
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
    
    def executeCommand(self, in_command = []):
        if in_command != []:
            print(f"Executing command: {in_command}")
        else:
            for command in self.command:
                print(f"Executing command: {command}")
            
