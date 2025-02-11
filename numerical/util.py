class printer:
    def __init__(self, H, d, K):
        self.H = H
        self.d = d
        self.K = K
        self.Uz = 0
    
    def setUz(self, Uz):
        self.Uz = Uz
    
    def toPos(self, Ux = 0, Uy = 0, Ua = 0, Ub = 0, Uc = 0, Ud = 0):
        if Ux == 0 and Uy == 0:
            Ux = self.Uz*Ua
            Uy = self.Uz*Ub
        x = self.K*Ux/self.Uz*(self.H**2)/self.d
        y = self.K*Uy/self.Uz*(self.H**2)/self.d
        return x, y
    
    def toU(self, x, y):
        Ux = x*self.d/(self.K*self.H**2)*self.Uz
        Uy = y*self.d/(self.K*self.H**2)*self.Uz
        return Ux, Uy
