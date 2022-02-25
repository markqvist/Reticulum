import RNS

class Interface:
    IN  = False
    OUT = False
    FWD = False
    RPT = False
    name = None

    MODE_FULL           = 0x01
    MODE_POINT_TO_POINT = 0x02
    MODE_ACCESS_POINT   = 0x03

    def __init__(self):
        self.rxb = 0
        self.txb = 0
        self.online = False

    def get_hash(self):
        return RNS.Identity.full_hash(str(self).encode("utf-8"))

    def detach(self):
        pass