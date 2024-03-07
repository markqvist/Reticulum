
from .Interface import Interface
from pubsub import pub
import os
import struct
import RNS

try:
    import meshtastic
    import meshtastic.serial_interface

    class MeshtasticInterface(Interface):

        FLAG_SPLIT = 0x01
        SEQ_UNSET = 0xFF

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

            self.HW_MTU = 233

            self.IN  = True
            self.OUT = False
            self.owner = owner
            self.name = name
            self.online = False
            # static default long-fast bitrate
            self.bitrate = 5469
            self.bitrate_kbps = 5.47

            self.buffer = None
            self.sequence = 0xFF
            self.ready = False

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
            RNS.log("Received Meshtastic packet of "+str(len(data))+" bytes: "+RNS.prettyhexrep(data), RNS.LOG_DEBUG)

            self.rxb += len(data)

            # check for fragmented packet
            header = data[0]
            split = (header & self.FLAG_SPLIT) == self.FLAG_SPLIT
            sequence = header >> 1
            RNS.log("incoming sequence: "+str(sequence), RNS.LOG_DEBUG)

            if split and self.sequence == self.SEQ_UNSET:
                # This is the first part of a split
                #  packet, so we set the self.sequence variable
                #  and add the data to the buffer.
                self.buffer = data[1:]
                self.sequence = sequence

                #last_rssi = LoRa.packetRssi();
                #last_snr_raw = LoRa.packetSnrRaw();

            elif split and self.sequence == sequence:
                # This is subsequent part of a split
                #  packet, so we add it to the buffer.
                self.buffer += data[1:]

                #last_rssi = (last_rssi+LoRa.packetRssi())/2;
                #last_snr_raw = (last_snr_raw+LoRa.packetSnrRaw())/2;

            elif not split and self.sequence == sequence:
                # This is not a split packet but it carries
                #  the last sequence id, so it must be the
                #  last part of a split packet.
                self.buffer += data[1:]
                self.sequence = self.SEQ_UNSET

                #last_rssi = LoRa.packetRssi();
                #last_snr_raw = LoRa.packetSnrRaw();

                # pass the buffer on to RNS
                RNS.log("Received Reticulum packet of "+str(len(self.buffer))+" bytes over Meshtastic interface", RNS.LOG_DEBUG)
                self.owner.inbound(self.buffer, self)
                self.buffer = None

            elif split and self.sequence != sequence:
                # This split packet does not carry the
                #  same sequence id, so we must assume
                #  that we are seeing the first part of
                #  a new split packet.
                # If we already had part of a split
                #  packet in the buffer then we clear it.
                if self.buffer != None:
                    RNS.log("Discarding incomplete buffer from previous split packet!", RNS.LOG_ERROR)
                self.buffer = data[1:]
                self.sequence = sequence

                #last_rssi = LoRa.packetRssi();
                #last_snr_raw = LoRa.packetSnrRaw();

            elif not split:
                # This is not a split packet, so we
                # just read it whole
                self.buffer = data[1:]
                self.sequence = self.SEQ_UNSET

                #last_rssi = LoRa.packetRssi();
                #last_snr_raw = LoRa.packetSnrRaw();

                # pass the buffer on to RNS
                RNS.log("Received Reticulum packet of "+str(len(self.buffer))+" bytes over Meshtastic interface", RNS.LOG_DEBUG)
                self.owner.inbound(self.buffer, self)
                self.buffer = None

        def processOutgoing(self, data):
            if self.interface == None:
                return
            RNS.log("Sending Reticulum packet of "+str(len(data))+" bytes over Meshtastic interface", RNS.LOG_DEBUG)

            header = int.from_bytes(os.urandom(1), "big") & 0xFE
            RNS.log("outgoing sequence: "+str(header >> 1), RNS.LOG_DEBUG)
            if len(data) > self.HW_MTU-1:
                header |= self.FLAG_SPLIT

            sent = 0
            while sent < len(data):
                size = len(data) - sent
                if size > self.HW_MTU-1:
                    size = self.HW_MTU-1
                # clear split flag for last part
                if sent+size >= len(data):
                    header &= ~self.FLAG_SPLIT
                buffer = struct.pack("!B", header) + data[sent:sent+size]
                sent += size

                RNS.log("Sending Meshtastic packet of "+str(len(buffer))+" bytes: "+RNS.prettyhexrep(buffer), RNS.LOG_DEBUG)
                try:
                    #self.interface.sendData(buffer)
                    self.interface.sendData(buffer, portNum=256, channelIndex=self.channel)
                    self.txb += len(buffer)
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

