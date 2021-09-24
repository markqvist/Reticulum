from .Interface import Interface
from time import sleep
import sys
import serial
import threading
import time
import RNS

class HDLC():
    # The Serial Interface packetizes data using
    # simplified HDLC framing, similar to PPP
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

class SerialInterface(Interface):
    MAX_CHUNK = 32768

    owner    = None
    port     = None
    speed    = None
    databits = None
    parity   = None
    stopbits = None
    serial   = None

    def __init__(self, owner, name, port, speed, databits, parity, stopbits):
        self.rxb = 0
        self.txb = 0
        
        self.serial   = None
        self.owner    = owner
        self.name     = name
        self.port     = port
        self.speed    = speed
        self.databits = databits
        self.parity   = serial.PARITY_NONE
        self.stopbits = stopbits
        self.timeout  = 100
        self.online   = False

        if parity.lower() == "e" or parity.lower() == "even":
            self.parity = serial.PARITY_EVEN

        if parity.lower() == "o" or parity.lower() == "odd":
            self.parity = serial.PARITY_ODD

        try:
            RNS.log("Opening serial port "+self.port+"...")
            self.serial = serial.Serial(
                port = self.port,
                baudrate = self.speed,
                bytesize = self.databits,
                parity = self.parity,
                stopbits = self.stopbits,
                xonxoff = False,
                rtscts = False,
                timeout = 0,
                inter_byte_timeout = None,
                write_timeout = None,
                dsrdtr = False,
            )
        except Exception as e:
            RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
            raise e

        if self.serial.is_open:
            sleep(0.5)
            thread = threading.Thread(target=self.readLoop)
            thread.setDaemon(True)
            thread.start()
            self.online = True
            RNS.log("Serial port "+self.port+" is now open")
        else:
            raise IOError("Could not open serial port")


    def processIncoming(self, data):
        self.rxb += len(data)            
        self.owner.inbound(data, self)


    def processOutgoing(self,data):
        if self.online:
            data = bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])
            written = self.serial.write(data)
            self.txb += len(data)            
            if written != len(data):
                raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))


    def readLoop(self):
        try:
            in_frame = False
            escape = False
            data_buffer = b""
            last_read_ms = int(time.time()*1000)

            while self.serial.is_open:
                if self.serial.in_waiting:
                    byte = ord(self.serial.read(1))
                    last_read_ms = int(time.time()*1000)

                    if (in_frame and byte == HDLC.FLAG):
                        in_frame = False
                        self.processIncoming(data_buffer)
                    elif (byte == HDLC.FLAG):
                        in_frame = True
                        data_buffer = b""
                    elif (in_frame and len(data_buffer) < RNS.Reticulum.MTU):
                        if (byte == HDLC.ESC):
                            escape = True
                        else:
                            if (escape):
                                if (byte == HDLC.FLAG ^ HDLC.ESC_MASK):
                                    byte = HDLC.FLAG
                                if (byte == HDLC.ESC  ^ HDLC.ESC_MASK):
                                    byte = HDLC.ESC
                                escape = False
                            data_buffer = data_buffer+bytes([byte])
                        
                else:
                    time_since_last = int(time.time()*1000) - last_read_ms
                    if len(data_buffer) > 0 and time_since_last > self.timeout:
                        data_buffer = b""
                        in_frame = False
                        escape = False
                    sleep(0.08)
        except Exception as e:
            self.online = False
            RNS.log("A serial port error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down. Restart Reticulum to attempt to open this interface again.", RNS.LOG_ERROR)

            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

    def __str__(self):
        return "SerialInterface["+self.name+"]"
