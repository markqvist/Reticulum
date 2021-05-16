import RNS

class Interface:
    IN  = False
    OUT = False
    FWD = False
    RPT = False
    name = None

    def __init__(self):
        pass

    def get_hash(self):
        # TODO: Maybe expand this to something more unique
        return RNS.Identity.full_hash(str(self).encode("utf-8"))