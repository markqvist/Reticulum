
from .Interface import Interface
from pubsub import pub
import time
import sys
import RNS

try:
    import meshtastic
    import meshtastic.serial_interface

    class MeshtasticInterface(Interface):

        @staticmethod
        def onReceive(packet, interface):
            if packet['decoded']['portnum'] == "PRIVATE_APP":
                interface.callback.processIncoming(packet['decoded']['payload'])

        def __init__(self, owner, name, config):
            super().__init__()

            self.port = config["port"] if "port" in config else None
            RNS.log("MeshtasticInterface: port="+str(self.port), RNS.LOG_DEBUG)
            self.channel = int(config["channel"]) if "channel" in config else 0
            RNS.log("MeshtasticInterface: channel="+str(self.channel), RNS.LOG_DEBUG)

            self.rxb = 0
            self.txb = 0

            self.HW_MTU = 256

            self.IN  = True
            self.OUT = False
            self.owner = owner
            self.name = name
            self.online = False
            # static default long-fast bitrate
            self.bitrate = 5469
            self.bitrate_kbps = 5.47

            self.interface = None

            try:
                RNS.log("Initializing Meshtastic interface...", RNS.LOG_DEBUG)
                # avoid api forcing app to terminate when no devices are found
                if self.port == None:
                    ports = meshtastic.util.findPorts(True)
                    if len(ports) == 0:
                        RNS.log("Failed to initialize Meshtastic interface! No devices found", RNS.LOG_ERROR)
                        return
                self.interface = meshtastic.serial_interface.SerialInterface(devPath=self.port)
                self.interface.callback = self

                RNS.log("Subscribing to Meshtastic events", RNS.LOG_DEBUG)
                pub.subscribe(self.onReceive, "meshtastic.receive.data")

            except Exception as e:
                RNS.log("Failed to initialize Meshtastic interface! "+str(e), RNS.LOG_ERROR)
                self.interface = None
                return

            RNS.log("Initialized Meshtastic interface!", RNS.LOG_DEBUG)

        def processIncoming(self, data):
            RNS.log("Received Meshtastic packet "+RNS.prettyhexrep(data), RNS.LOG_DEBUG)
            self.rxb += len(data)
            self.owner.inbound(data, self)

        def processOutgoing(self, data):
            if self.interface == None:
                return
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

except ImportError:

    class MeshtasticInterface(Interface):

        def __init__(self, owner, name, port=None, channel=0):
            super().__init__()

            RNS.log("Failed to initialize Meshtastic interface! Meshtastic API is not installed", RNS.LOG_ERROR)
            #raise OSError("Meshtastic API is not installed")

        def processOutgoing(self, data):
            return

        def __str__(self):
            if self.port == None:
                return "MeshtasticInterface["+self.name+"]"
            return "MeshtasticInterface["+self.name+"/"+self.port+"]"

