# MIT License
#
# Copyright (c) 2016-2022 Mark Qvist / unsigned.io
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from RNS.Interfaces.Interface import Interface
from time import sleep
import sys
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
        import importlib
        if RNS.vendor.platformutils.is_android():
            self.on_android  = True
            if importlib.util.find_spec('usbserial4a') != None:
                if importlib.util.find_spec('jnius') == None:
                    RNS.log("Could not load jnius API wrapper for Android, Serial interface cannot be created.", RNS.LOG_CRITICAL)
                    RNS.log("This probably means you are trying to use an USB-based interface from within Termux or similar.", RNS.LOG_CRITICAL)
                    RNS.log("This is currently not possible, due to this environment limiting access to the native Android APIs.", RNS.LOG_CRITICAL)
                    RNS.panic()

                from usbserial4a import serial4a as serial
                self.parity = "N"
            
            else:
                RNS.log("Could not load USB serial module for Android, Serial interface cannot be created.", RNS.LOG_CRITICAL)
                RNS.log("You can install this module by issuing: pip install usbserial4a", RNS.LOG_CRITICAL)
                RNS.panic()
        else:
            raise SystemError("Android-specific interface was used on non-Android OS")

        self.rxb = 0
        self.txb = 0

        self.HW_MTU = 564
        
        self.pyserial = serial
        self.serial   = None
        self.owner    = owner
        self.name     = name
        self.port     = port
        self.speed    = speed
        self.databits = databits
        self.parity   = "N"
        self.stopbits = stopbits
        self.timeout  = 100
        self.online   = False
        self.bitrate  = self.speed

        if parity.lower() == "e" or parity.lower() == "even":
            self.parity = "E"

        if parity.lower() == "o" or parity.lower() == "odd":
            self.parity = "O"

        try:
            self.open_port()
        except Exception as e:
            RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
            raise e

        if self.serial.is_open:
            self.configure_device()
        else:
            raise IOError("Could not open serial port")


    def open_port(self):
        RNS.log("Opening serial port "+self.port+"...")
        # Get device parameters
        from usb4a import usb
        device = usb.get_usb_device(self.port)
        if device:
            vid = device.getVendorId()
            pid = device.getProductId()

            # Driver overrides for speficic chips
            proxy = self.pyserial.get_serial_port
            if vid == 0x1A86 and pid == 0x55D4:
                # Force CDC driver for Qinheng CH34x
                RNS.log(str(self)+" using CDC driver for "+RNS.hexrep(vid)+":"+RNS.hexrep(pid), RNS.LOG_DEBUG)
                from usbserial4a.cdcacmserial4a import CdcAcmSerial
                proxy = CdcAcmSerial

            self.serial = proxy(
                self.port,
                baudrate = self.speed,
                bytesize = self.databits,
                parity = self.parity,
                stopbits = self.stopbits,
                xonxoff = False,
                rtscts = False,
                timeout = None,
                inter_byte_timeout = None,
                # write_timeout = wtimeout,
                dsrdtr = False,
            )

            if vid == 0x0403:
                # Hardware parameters for FTDI devices @ 115200 baud
                self.serial.DEFAULT_READ_BUFFER_SIZE = 16 * 1024
                self.serial.USB_READ_TIMEOUT_MILLIS = 100
                self.serial.timeout = 0.1
            elif vid == 0x10C4:
                # Hardware parameters for SiLabs CP210x @ 115200 baud
                self.serial.DEFAULT_READ_BUFFER_SIZE = 64 
                self.serial.USB_READ_TIMEOUT_MILLIS = 12
                self.serial.timeout = 0.012
            elif vid == 0x1A86 and pid == 0x55D4:
                # Hardware parameters for Qinheng CH34x @ 115200 baud
                self.serial.DEFAULT_READ_BUFFER_SIZE = 64
                self.serial.USB_READ_TIMEOUT_MILLIS = 12
                self.serial.timeout = 0.1
            else:
                # Default values
                self.serial.DEFAULT_READ_BUFFER_SIZE = 1 * 1024
                self.serial.USB_READ_TIMEOUT_MILLIS = 100
                self.serial.timeout = 0.1

            RNS.log(str(self)+" USB read buffer size set to "+RNS.prettysize(self.serial.DEFAULT_READ_BUFFER_SIZE), RNS.LOG_DEBUG)
            RNS.log(str(self)+" USB read timeout set to "+str(self.serial.USB_READ_TIMEOUT_MILLIS)+"ms", RNS.LOG_DEBUG)
            RNS.log(str(self)+" USB write timeout set to "+str(self.serial.USB_WRITE_TIMEOUT_MILLIS)+"ms", RNS.LOG_DEBUG)

    def configure_device(self):
        sleep(0.5)
        thread = threading.Thread(target=self.readLoop)
        thread.daemon = True
        thread.start()
        self.online = True
        RNS.log("Serial port "+self.port+" is now open", RNS.LOG_VERBOSE)


    def processIncoming(self, data):
        self.rxb += len(data)
        def af():
            self.owner.inbound(data, self)
        threading.Thread(target=af, daemon=True).start()

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
                serial_bytes = self.serial.read()
                got = len(serial_bytes)

                for byte in serial_bytes:
                    last_read_ms = int(time.time()*1000)

                    if (in_frame and byte == HDLC.FLAG):
                        in_frame = False
                        self.processIncoming(data_buffer)
                    elif (byte == HDLC.FLAG):
                        in_frame = True
                        data_buffer = b""
                    elif (in_frame and len(data_buffer) < self.HW_MTU):
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
                        
                if got == 0:
                    time_since_last = int(time.time()*1000) - last_read_ms
                    if len(data_buffer) > 0 and time_since_last > self.timeout:
                        data_buffer = b""
                        in_frame = False
                        escape = False
                    # sleep(0.08)
                    
        except Exception as e:
            self.online = False
            RNS.log("A serial port error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is now offline.", RNS.LOG_ERROR)
            
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)

        self.online = False
        self.serial.close()
        self.reconnect_port()

    def reconnect_port(self):
        while not self.online:
            try:
                time.sleep(5)
                RNS.log("Attempting to reconnect serial port "+str(self.port)+" for "+str(self)+"...", RNS.LOG_VERBOSE)
                self.open_port()
                if self.serial.is_open:
                    self.configure_device()
            except Exception as e:
                RNS.log("Error while reconnecting port, the contained exception was: "+str(e), RNS.LOG_ERROR)

        RNS.log("Reconnected serial port for "+str(self))

    def __str__(self):
        return "SerialInterface["+self.name+"]"
