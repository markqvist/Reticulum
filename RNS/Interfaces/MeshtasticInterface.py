
from .Interface import Interface
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time
import sys
import RNS


class MeshtasticInterface(Interface):

    @staticmethod
    def onReceive(packet, interface):
        #print(f"Received: {packet}")
        if packet['decoded']['portnum'] == "PRIVATE_APP":
            interface.callback.processIncoming(packet['decoded']['payload'])

    def __init__(self, owner, name, port=None, channel=0):
        super().__init__()

        self.rxb = 0
        self.txb = 0

        self.HW_MTU = 256

        self.IN  = True
        self.OUT = False
        self.owner = owner
        self.name = name
        self.port = port
        self.channel = channel
        self.online = False
        # static default long-fast bitrate
        self.bitrate = 5469
        self.bitrate_kbps = 5.47

        RNS.log("Initializing Meshtastic interface...", RNS.LOG_DEBUG)
        self.interface = meshtastic.serial_interface.SerialInterface(devPath=port)
        self.interface.callback = self

        RNS.log("Subscribing to Meshtastic events", RNS.LOG_DEBUG)
        pub.subscribe(self.onReceive, "meshtastic.receive.data")

        RNS.log("Initialized Meshtastic interface!", RNS.LOG_DEBUG)

    def processIncoming(self, data):
        RNS.log("Received Meshtastic packet "+RNS.prettyhexrep(data), RNS.LOG_DEBUG)
        self.rxb += len(data)
        self.owner.inbound(data, self)

    def processOutgoing(self, data):
        RNS.log("Sending Meshtastic packet "+RNS.prettyhexrep(data), RNS.LOG_DEBUG)
        try:
            #self.interface.sendData(data)
            self.interface.sendData(data, portNum=256, channelIndex=self.channel)
            self.txb += len(data)
            
        except Exception as e:
            RNS.log("Could not transmit on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def __str__(self):
        if self.port == None:
            return "MeshtasticInterface["+self.name+"]"
        return "MeshtasticInterface["+self.name+"/"+self.port+"]"

