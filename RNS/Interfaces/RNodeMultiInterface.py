# MIT License
#
# Copyright (c) 2024 Jacob Eva. Adapted from the RNodeInterface by Mark Qvist / unsigned.io
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

from .Interface import Interface
from time import sleep
import sys
import threading
import time
import math
import RNS

class KISS():
    FEND            = 0xC0
    FESC            = 0xDB
    TFEND           = 0xDC
    TFESC           = 0xDD
    
    CMD_UNKNOWN     = 0xFE
    CMD_FREQUENCY   = 0x01
    CMD_BANDWIDTH   = 0x02
    CMD_TXPOWER     = 0x03
    CMD_SF          = 0x04
    CMD_CR          = 0x05
    CMD_RADIO_STATE = 0x06
    CMD_RADIO_LOCK  = 0x07
    CMD_ST_ALOCK    = 0x0B
    CMD_LT_ALOCK    = 0x0C
    CMD_DETECT      = 0x08
    CMD_LEAVE       = 0x0A
    CMD_READY       = 0x0F
    CMD_STAT_RX     = 0x21
    CMD_STAT_TX     = 0x22
    CMD_STAT_RSSI   = 0x23
    CMD_STAT_SNR    = 0x24
    CMD_STAT_CHTM   = 0x25
    CMD_STAT_PHYPRM = 0x26
    CMD_BLINK       = 0x30
    CMD_RANDOM      = 0x40
    CMD_FB_EXT      = 0x41
    CMD_FB_READ     = 0x42
    CMD_FB_WRITE    = 0x43
    CMD_BT_CTRL     = 0x46
    CMD_PLATFORM    = 0x48
    CMD_MCU         = 0x49
    CMD_FW_VERSION  = 0x50
    CMD_ROM_READ    = 0x51
    CMD_RESET       = 0x55
    CMD_INTERFACES  = 0x64

    CMD_INT0_DATA   = 0x00
    CMD_INT1_DATA   = 0x10
    CMD_INT2_DATA   = 0x20
    CMD_INT3_DATA   = 0x70
    CMD_INT4_DATA   = 0x75
    CMD_INT5_DATA   = 0x90
    CMD_INT6_DATA   = 0xA0
    CMD_INT7_DATA   = 0xB0
    CMD_INT8_DATA   = 0xC0
    CMD_INT9_DATA   = 0xD0
    CMD_INT10_DATA  = 0xE0
    CMD_INT11_DATA  = 0xF0

    CMD_SEL_INT0    = 0x1E
    CMD_SEL_INT1    = 0x1F
    CMD_SEL_INT2    = 0x2F
    CMD_SEL_INT3    = 0x74
    CMD_SEL_INT4    = 0x7F
    CMD_SEL_INT5    = 0x9F
    CMD_SEL_INT6    = 0xAF
    CMD_SEL_INT7    = 0xBF
    CMD_SEL_INT8    = 0xCF
    CMD_SEL_INT9    = 0xDF
    CMD_SEL_INT10   = 0xEF
    CMD_SEL_INT11   = 0xFF

    DETECT_REQ      = 0x73
    DETECT_RESP     = 0x46
    
    RADIO_STATE_OFF = 0x00
    RADIO_STATE_ON  = 0x01
    RADIO_STATE_ASK = 0xFF
    
    CMD_ERROR           = 0x90
    ERROR_INITRADIO     = 0x01
    ERROR_TXFAILED      = 0x02
    ERROR_EEPROM_LOCKED = 0x03

    PLATFORM_AVR   = 0x90
    PLATFORM_ESP32 = 0x80
    PLATFORM_NRF52 = 0x70

    SX127X    = 0x00
    SX1276    = 0x01
    SX1278    = 0x02
    SX126X    = 0x10
    SX1262    = 0x11
    SX128X    = 0x20
    SX1280    = 0x21

    def int_data_cmd_to_index(int_data_cmd):
        if int_data_cmd == KISS.CMD_INT0_DATA:
            return 0
        elif int_data_cmd == KISS.CMD_INT1_DATA:
            return 1
        elif int_data_cmd == KISS.CMD_INT2_DATA:
            return 2
        elif int_data_cmd == KISS.CMD_INT3_DATA:
            return 3
        elif int_data_cmd == KISS.CMD_INT4_DATA:
            return 4
        elif int_data_cmd == KISS.CMD_INT5_DATA:
            return 5
        elif int_data_cmd == KISS.CMD_INT6_DATA:
            return 6
        elif int_data_cmd == KISS.CMD_INT7_DATA:
            return 7
        elif int_data_cmd == KISS.CMD_INT8_DATA:
            return 8
        elif int_data_cmd == KISS.CMD_INT9_DATA:
            return 9
        elif int_data_cmd == KISS.CMD_INT10_DATA:
            return 10
        elif int_data_cmd == KISS.CMD_INT11_DATA:
            return 11
        else:
            return 0

    def interface_type_to_str(interface_type):
        if interface_type == KISS.SX126X or interface_type == KISS.SX1262:
                return "SX126X"
        elif interface_type == KISS.SX127X or interface_type == KISS.SX1276 or interface_type == KISS.SX1278:
            return "SX127X"
        elif interface_type == KISS.SX128X or interface_type == KISS.SX1280:
            return "SX128X"
        else:
            return "SX127X"

    @staticmethod
    def escape(data):
        data = data.replace(bytes([0xdb]), bytes([0xdb, 0xdd]))
        data = data.replace(bytes([0xc0]), bytes([0xdb, 0xdc]))
        return data
    

class RNodeMultiInterface(Interface):
    MAX_CHUNK = 32768

    CALLSIGN_MAX_LEN    = 32

    REQUIRED_FW_VER_MAJ = 1
    REQUIRED_FW_VER_MIN = 74

    RECONNECT_WAIT = 5

    MAX_SUBINTERFACES = 11

    def __init__(self, owner, name, port, subint_config, id_interval = None, id_callsign = None):
        if RNS.vendor.platformutils.is_android():
            raise SystemError("Invalid interface type. The Android-specific RNode interface must be used on Android")

        import importlib
        if importlib.util.find_spec('serial') != None:
            import serial
        else:
            RNS.log("Using the RNode interface requires a serial communication module to be installed.", RNS.LOG_CRITICAL)
            RNS.log("You can install one with the command: python3 -m pip install pyserial", RNS.LOG_CRITICAL)
            RNS.panic()

        super().__init__()

        self.HW_MTU = 508
        
        self.clients = 0
        self.pyserial    = serial
        self.serial      = None
        self.selected_index = 0
        self.owner       = owner
        self.name        = name
        self.port        = port
        self.speed       = 115200
        self.databits    = 8
        self.stopbits    = 1
        self.timeout     = 100
        self.online      = False
        self.detached    = False
        self.reconnecting= False

        self.bitrate     = 0
        self.platform    = None
        self.display     = None
        self.mcu         = None
        self.detected    = False
        self.firmware_ok = False
        self.maj_version = 0
        self.min_version = 0
        self.mode        = RNS.Interfaces.Interface.Interface.MODE_FULL

        self.last_id     = 0
        self.first_tx    = None
        self.reconnect_w = RNodeMultiInterface.RECONNECT_WAIT

        self.subinterfaces = [0] * RNodeMultiInterface.MAX_SUBINTERFACES
        self.subinterface_types = []
        self.subint_config = subint_config

        self.r_stat_rx   = None
        self.r_stat_tx   = None
        self.r_stat_rssi = None
        self.r_stat_snr  = None
        self.r_st_alock  = None
        self.r_lt_alock  = None
        self.r_random    = None

        self.packet_queue    = []
        self.interface_ready = False
        self.announce_rate_target = None

        self.validcfg  = True
        if id_interval != None and id_callsign != None:
            if (len(id_callsign.encode("utf-8")) <= RNodeMultiInterface.CALLSIGN_MAX_LEN):
                self.should_id = True
                self.id_callsign = id_callsign.encode("utf-8")
                self.id_interval = id_interval
            else:
                RNS.log("The encoded ID callsign for "+str(self)+" exceeds the max length of "+str(RNodeMultiInterface.CALLSIGN_MAX_LEN)+" bytes.", RNS.LOG_ERROR)
                self.validcfg = False
        else:
            self.id_interval = None
            self.id_callsign = None

        if (not self.validcfg):
            raise ValueError("The configuration for "+str(self)+" contains errors, interface is offline")

    def start(self):
        try:
            self.open_port()

            if self.serial.is_open:
                self.configure_device()
            else:
                raise IOError("Could not open serial port")

        except Exception as e:
            RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("Reticulum will attempt to bring up this interface periodically", RNS.LOG_ERROR)
            if not self.detached and not self.reconnecting:
                thread = threading.Thread(target=self.reconnect_port)
                thread.daemon = True
                thread.start()

    def open_port(self):
        RNS.log("Opening serial port "+self.port+"...")
        self.serial = self.pyserial.Serial(
            port = self.port,
            baudrate = self.speed,
            bytesize = self.databits,
            parity = self.pyserial.PARITY_NONE,
            stopbits = self.stopbits,
            xonxoff = False,
            rtscts = False,
            timeout = 0,
            inter_byte_timeout = None,
            write_timeout = None,
            dsrdtr = False,
        )


    def configure_device(self):
        sleep(2.0)

        thread = threading.Thread(target=self.readLoop)
        thread.daemon = True
        thread.start()

        self.detect()
        sleep(0.2)
        
        if not self.detected:
            RNS.log("Could not detect device for "+str(self), RNS.LOG_ERROR)
            self.serial.close()
        else:
            if self.platform == KISS.PLATFORM_ESP32 or self.platform == KISS.PLATFORM_NRF52:
                self.display = True

        RNS.log("Serial port "+self.port+" is now open")
        RNS.log("Creating subinterfaces...", RNS.LOG_VERBOSE)
        for subint in self.subint_config:
            subint_vport = int(subint[1])
            # check if index of vport exists in interface types array (the index corresponds to the vport for that interface)
            if len(self.subinterface_types) >= (subint_vport+1):
                # interface will add itself to the subinterfaces list automatically
                interface = RNodeSubInterface(
                        RNS.Transport,
                        subint[0],
                        self,
                        subint_vport,
                        self.subinterface_types[subint_vport],
                        frequency = subint[2],
                        bandwidth = subint[3],
                        txpower = subint[4],
                        sf = subint[5],
                        cr = subint[6],
                        flow_control=subint[7],
                        st_alock=subint[8],
                        lt_alock=subint[9]
                )

                interface.OUT = subint[10]
                interface.IN  = True
                
                interface.announce_rate_target = self.announce_rate_target
                interface.mode = self.mode
                interface.HW_MTU = self.HW_MTU
                interface.detected = True
                RNS.Transport.interfaces.append(interface)
                RNS.log("Spawned new RNode subinterface: "+str(interface), RNS.LOG_VERBOSE)

                self.clients += 1
            else:
                raise ValueError("Virtual port \""+subint[1]+"\" for subinterface "+subint[0]+" does not exist on "+self.name)
        self.online = True

    def detect(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_DETECT, KISS.DETECT_REQ, KISS.FEND, KISS.CMD_FW_VERSION, 0x00, KISS.FEND, KISS.CMD_PLATFORM, 0x00, KISS.FEND, KISS.CMD_MCU, 0x00, KISS.FEND, KISS.CMD_INTERFACES, 0x00, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while detecting hardware for "+str(self))
    
    def leave(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_LEAVE, 0xFF, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending host left command to device")
    
    def enable_external_framebuffer(self):
        if self.display != None:
            kiss_command = bytes([KISS.FEND, KISS.CMD_FB_EXT, 0x01, KISS.FEND])
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while enabling external framebuffer on device")

    def disable_external_framebuffer(self):
        if self.display != None:
            kiss_command = bytes([KISS.FEND, KISS.CMD_FB_EXT, 0x00, KISS.FEND])
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while disabling external framebuffer on device")

    FB_PIXEL_WIDTH     = 64
    FB_BITS_PER_PIXEL  = 1
    FB_PIXELS_PER_BYTE = 8//FB_BITS_PER_PIXEL
    FB_BYTES_PER_LINE  = FB_PIXEL_WIDTH//FB_PIXELS_PER_BYTE
    def display_image(self, imagedata):
        if self.display != None:
            lines = len(imagedata)//8
            for line in range(lines):
                line_start = line*RNodeMultiInterface.FB_BYTES_PER_LINE
                line_end   = line_start+RNodeMultiInterface.FB_BYTES_PER_LINE
                line_data = bytes(imagedata[line_start:line_end])
                self.write_framebuffer(line, line_data)

    def write_framebuffer(self, line, line_data):
        if self.display != None:
            line_byte = line.to_bytes(1, byteorder="big", signed=False)
            data = line_byte+line_data
            escaped_data = KISS.escape(data)
            kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_FB_WRITE])+escaped_data+bytes([KISS.FEND])
            
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while writing framebuffer data device")

    def hard_reset(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_RESET, 0xf8, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while restarting device")
        sleep(2.25);

    def setFrequency(self, frequency, interface):
        c1 = frequency >> 24
        c2 = frequency >> 16 & 0xFF
        c3 = frequency >> 8 & 0xFF
        c4 = frequency & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_FREQUENCY])+data+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring frequency for "+str(self))
        self.selected_index = interface.index

    def setBandwidth(self, bandwidth, interface):
        c1 = bandwidth >> 24
        c2 = bandwidth >> 16 & 0xFF
        c3 = bandwidth >> 8 & 0xFF
        c4 = bandwidth & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_BANDWIDTH])+data+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring bandwidth for "+str(self))
        self.selected_index = interface.index

    def setTXPower(self, txpower, interface):
        txp = txpower.to_bytes(1, byteorder="big", signed=True)
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_TXPOWER])+txp+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring TX power for "+str(self))
        self.selected_index = interface.index

    def setSpreadingFactor(self, sf, interface):
        sf = bytes([sf])
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_SF])+sf+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring spreading factor for "+str(self))
        self.selected_index = interface.index

    def setCodingRate(self, cr, interface):
        cr = bytes([cr])
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_CR])+cr+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring coding rate for "+str(self))
        self.selected_index = interface.index

    def setSTALock(self, st_alock, interface):
        if st_alock != None:
            at = int(st_alock*100)
            c1 = at >> 8 & 0xFF
            c2 = at & 0xFF
            data = KISS.escape(bytes([c1])+bytes([c2]))

            kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_ST_ALOCK])+data+bytes([KISS.FEND])
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while configuring short-term airtime limit for "+str(self))
            self.selected_index = interface.index

    def setLTALock(self, lt_alock, interface):
        if lt_alock != None:
            at = int(lt_alock*100)
            c1 = at >> 8 & 0xFF
            c2 = at & 0xFF
            data = KISS.escape(bytes([c1])+bytes([c2]))

            kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_LT_ALOCK])+data+bytes([KISS.FEND])
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while configuring long-term airtime limit for "+str(self))
            self.selected_index = interface.index

    def setRadioState(self, state, interface):
        #self.state = state
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_RADIO_STATE])+bytes([state])+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring radio state for "+str(self))
        self.selected_index = interface.index

    def validate_firmware(self):
        if (self.maj_version >= RNodeMultiInterface.REQUIRED_FW_VER_MAJ):
            if (self.min_version >= RNodeMultiInterface.REQUIRED_FW_VER_MIN):
                self.firmware_ok = True
        
        if self.firmware_ok:
            return

        RNS.log("The firmware version of the connected RNode is "+str(self.maj_version)+"."+str(self.min_version), RNS.LOG_ERROR)
        RNS.log("This version of Reticulum requires at least version "+str(RNodeMultiInterface.REQUIRED_FW_VER_MAJ)+"."+str(RNodeMultiInterface.REQUIRED_FW_VER_MIN), RNS.LOG_ERROR)
        RNS.log("Please update your RNode firmware with rnodeconf from https://github.com/markqvist/Reticulum/RNS/Utilities/rnodeconf.py")
        RNS.panic()

    def processOutgoing(self, data, interface = None):
        if interface is None:
            # do nothing if RNS tries to transmit on this interface directly
            pass
        else:
            data    = KISS.escape(data)
            frame   = bytes([0xc0])+bytes([interface.data_cmd])+data+bytes([0xc0])

            written = self.serial.write(frame)
            self.txb += len(data)

            if written != len(frame):
                raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))

    def received_announce(self, from_spawned=False):
        if from_spawned: self.ia_freq_deque.append(time.time())

    def sent_announce(self, from_spawned=False):
        if from_spawned: self.oa_freq_deque.append(time.time())

    def readLoop(self):
        try:
            in_frame = False
            escape = False
            command = KISS.CMD_UNKNOWN
            data_buffer = b""
            command_buffer = b""
            last_read_ms = int(time.time()*1000)

            while self.serial.is_open:
                if self.serial.in_waiting:
                    byte = ord(self.serial.read(1))
                    last_read_ms = int(time.time()*1000)

                    if (in_frame and byte == KISS.FEND and
                            (command == KISS.CMD_INT0_DATA or
                            command == KISS.CMD_INT1_DATA or
                            command == KISS.CMD_INT2_DATA or
                            command == KISS.CMD_INT3_DATA or
                            command == KISS.CMD_INT4_DATA or
                            command == KISS.CMD_INT5_DATA or
                            command == KISS.CMD_INT6_DATA or
                            command == KISS.CMD_INT7_DATA or
                            command == KISS.CMD_INT8_DATA or
                            command == KISS.CMD_INT9_DATA or
                            command == KISS.CMD_INT10_DATA or
                            command == KISS.CMD_INT11_DATA)):
                        in_frame = False
                        self.subinterfaces[KISS.int_data_cmd_to_index(command)].processIncoming(data_buffer)
                        self.selected_index = KISS.int_data_cmd_to_index(command)
                        data_buffer = b""
                        command_buffer = b""
                    elif (byte == KISS.FEND):
                        in_frame = True
                        command = KISS.CMD_UNKNOWN
                        data_buffer = b""
                        command_buffer = b""
                    elif (in_frame and len(data_buffer) < self.HW_MTU):
                        if (len(data_buffer) == 0 and command == KISS.CMD_UNKNOWN):
                            command = byte
                        elif (command == KISS.CMD_INT0_DATA or
                              command == KISS.CMD_INT1_DATA or
                              command == KISS.CMD_INT2_DATA or
                              command == KISS.CMD_INT3_DATA or
                              command == KISS.CMD_INT4_DATA or
                              command == KISS.CMD_INT5_DATA or
                              command == KISS.CMD_INT6_DATA or
                              command == KISS.CMD_INT7_DATA or
                              command == KISS.CMD_INT8_DATA or
                              command == KISS.CMD_INT9_DATA or
                              command == KISS.CMD_INT10_DATA or
                              command == KISS.CMD_INT11_DATA):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                data_buffer = data_buffer+bytes([byte])
                        elif (command == KISS.CMD_FREQUENCY):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 4):
                                    self.subinterfaces[self.selected_index].r_frequency = command_buffer[0] << 24 | command_buffer[1] << 16 | command_buffer[2] << 8 | command_buffer[3]
                                    RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting frequency is "+str(self.subinterfaces[self.selected_index].r_frequency/1000000.0)+" MHz", RNS.LOG_DEBUG)
                                    self.subinterfaces[self.selected_index].updateBitrate()

                        elif (command == KISS.CMD_BANDWIDTH):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 4):
                                    self.subinterfaces[self.selected_index].r_bandwidth = command_buffer[0] << 24 | command_buffer[1] << 16 | command_buffer[2] << 8 | command_buffer[3]
                                    RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting bandwidth is "+str(self.subinterfaces[self.selected_index].r_bandwidth/1000.0)+" KHz", RNS.LOG_DEBUG)
                                    self.subinterfaces[self.selected_index].updateBitrate()

                        elif (command == KISS.CMD_TXPOWER):
                            txp = byte - 256 if byte > 127 else byte
                            self.subinterfaces[self.selected_index].r_txpower = txp
                            RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting TX power is "+str(self.subinterfaces[self.selected_index].r_txpower)+" dBm", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_SF):
                            self.subinterfaces[self.selected_index].r_sf = byte
                            RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting spreading factor is "+str(self.subinterfaces[self.selected_index].r_sf), RNS.LOG_DEBUG)
                            self.subinterfaces[self.selected_index].updateBitrate()
                        elif (command == KISS.CMD_CR):
                            self.subinterfaces[self.selected_index].r_cr = byte
                            RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting coding rate is "+str(self.subinterfaces[self.selected_index].r_cr), RNS.LOG_DEBUG)
                            self.subinterfaces[self.selected_index].updateBitrate()
                        elif (command == KISS.CMD_RADIO_STATE):
                            self.subinterfaces[self.selected_index].r_state = byte
                            if self.subinterfaces[self.selected_index].r_state:
                                pass
                                #RNS.log(str(self)+" Radio reporting state is online", RNS.LOG_DEBUG)
                            else:
                                RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting state is offline", RNS.LOG_DEBUG)

                        elif (command == KISS.CMD_RADIO_LOCK):
                            self.subinterfaces[self.selected_index].r_lock = byte
                        elif (command == KISS.CMD_FW_VERSION):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 2):
                                    self.maj_version = int(command_buffer[0])
                                    self.min_version = int(command_buffer[1])
                                    self.validate_firmware()

                        # not implemented in RNode_Firmware yet
                        #elif (command == KISS.CMD_STAT_RX):
                        #    if (byte == KISS.FESC):
                        #        escape = True
                        #    else:
                        #        if (escape):
                        #            if (byte == KISS.TFEND):
                        #                byte = KISS.FEND
                        #            if (byte == KISS.TFESC):
                        #                byte = KISS.FESC
                        #            escape = False
                        #        command_buffer = command_buffer+bytes([byte])
                        #        if (len(command_buffer) == 4):
                        #            self.r_stat_rx = ord(command_buffer[0]) << 24 | ord(command_buffer[1]) << 16 | ord(command_buffer[2]) << 8 | ord(command_buffer[3])

                        #elif (command == KISS.CMD_STAT_TX):
                        #    if (byte == KISS.FESC):
                        #        escape = True
                        #    else:
                        #        if (escape):
                        #            if (byte == KISS.TFEND):
                        #                byte = KISS.FEND
                        #            if (byte == KISS.TFESC):
                        #                byte = KISS.FESC
                        #            escape = False
                        #        command_buffer = command_buffer+bytes([byte])
                        #        if (len(command_buffer) == 4):
                        #            self.r_stat_tx = ord(command_buffer[0]) << 24 | ord(command_buffer[1]) << 16 | ord(command_buffer[2]) << 8 | ord(command_buffer[3])

                        elif (command == KISS.CMD_STAT_RSSI):
                            self.subinterfaces[self.selected_index].r_stat_rssi = byte-RNodeSubInterface.RSSI_OFFSET
                        elif (command == KISS.CMD_STAT_SNR):
                            self.subinterfaces[self.selected_index].r_stat_snr = int.from_bytes(bytes([byte]), byteorder="big", signed=True) * 0.25
                            try:
                                sfs = self.subinterfaces[self.selected_index].r_sf-7
                                snr = self.subinterfaces[self.selected_index].r_stat_snr
                                q_snr_min = RNodeSubInterface.Q_SNR_MIN_BASE-sfs*RNodeSubInterface.Q_SNR_STEP
                                q_snr_max = RNodeSubInterface.Q_SNR_MAX
                                q_snr_span = q_snr_max-q_snr_min
                                quality = round(((snr-q_snr_min)/(q_snr_span))*100,1)
                                if quality > 100.0: quality = 100.0
                                if quality < 0.0: quality = 0.0
                                self.subinterfaces[self.selected_index].r_stat_q = quality
                            except:
                                pass
                        elif (command == KISS.CMD_ST_ALOCK):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 2):
                                    at = command_buffer[0] << 8 | command_buffer[1]
                                    self.subinterfaces[self.selected_index].r_st_alock = at/100.0
                                    RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting short-term airtime limit is "+str(self.subinterfaces[self.selected_index].r_st_alock)+"%", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_LT_ALOCK):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 2):
                                    at = command_buffer[0] << 8 | command_buffer[1]
                                    self.subinterfaces[self.selected_index].r_lt_alock = at/100.0
                                    RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting long-term airtime limit is "+str(self.subinterfaces[self.selected_index].r_lt_alock)+"%", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_STAT_CHTM):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 8):
                                    ats = command_buffer[0] << 8 | command_buffer[1]
                                    atl = command_buffer[2] << 8 | command_buffer[3]
                                    cus = command_buffer[4] << 8 | command_buffer[5]
                                    cul = command_buffer[6] << 8 | command_buffer[7]
                                    
                                    self.r_airtime_short      = ats/100.0
                                    self.r_airtime_long       = atl/100.0
                                    self.r_channel_load_short = cus/100.0
                                    self.r_channel_load_long  = cul/100.0
                        elif (command == KISS.CMD_STAT_PHYPRM):
                            if (byte == KISS.FESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == KISS.TFEND):
                                        byte = KISS.FEND
                                    if (byte == KISS.TFESC):
                                        byte = KISS.FESC
                                    escape = False
                                command_buffer = command_buffer+bytes([byte])
                                if (len(command_buffer) == 10):
                                    lst = (command_buffer[0] << 8 | command_buffer[1])/1000.0
                                    lsr = command_buffer[2] << 8 | command_buffer[3]
                                    prs = command_buffer[4] << 8 | command_buffer[5]
                                    prt = command_buffer[6] << 8 | command_buffer[7]
                                    cst = command_buffer[8] << 8 | command_buffer[9]

                                    if lst != self.subinterfaces[self.selected_index].r_symbol_time_ms or lsr != self.subinterfaces[self.selected_index].r_symbol_rate or prs != self.subinterfaces[self.selected_index].r_preamble_symbols or prt != self.subinterfaces[self.selected_index].r_premable_time_ms or cst != self.subinterfaces[self.selected_index].r_csma_slot_time_ms:
                                        self.subinterfaces[self.selected_index].r_symbol_time_ms    = lst
                                        self.subinterfaces[self.selected_index].r_symbol_rate       = lsr
                                        self.subinterfaces[self.selected_index].r_preamble_symbols  = prs
                                        self.subinterfaces[self.selected_index].r_premable_time_ms  = prt
                                        self.subinterfaces[self.selected_index].r_csma_slot_time_ms = cst
                                        RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting symbol time is "+str(round(self.subinterfaces[self.selected_index].r_symbol_time_ms,2))+"ms (at "+str(self.subinterfaces[self.selected_index].r_symbol_rate)+" baud)", RNS.LOG_DEBUG)
                                        RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting preamble is "+str(self.subinterfaces[self.selected_index].r_preamble_symbols)+" symbols ("+str(self.subinterfaces[self.selected_index].r_premable_time_ms)+"ms)", RNS.LOG_DEBUG)
                                        RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting CSMA slot time is "+str(self.subinterfaces[self.selected_index].r_csma_slot_time_ms)+"ms", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_RANDOM):
                            self.r_random = byte
                        elif (command == KISS.CMD_PLATFORM):
                            self.platform = byte
                        elif (command == KISS.CMD_MCU):
                            self.mcu = byte
                        elif (command == KISS.CMD_ERROR):
                            if (byte == KISS.ERROR_INITRADIO):
                                RNS.log(str(self)+" hardware initialisation error (code "+RNS.hexrep(byte)+")", RNS.LOG_ERROR)
                                raise IOError("Radio initialisation failure")
                            elif (byte == KISS.ERROR_TXFAILED):
                                RNS.log(str(self)+" hardware TX error (code "+RNS.hexrep(byte)+")", RNS.LOG_ERROR)
                                raise IOError("Hardware transmit failure")
                            else:
                                RNS.log(str(self)+" hardware error (code "+RNS.hexrep(byte)+")", RNS.LOG_ERROR)
                                raise IOError("Unknown hardware failure")
                        elif (command == KISS.CMD_RESET):
                            if (byte == 0xF8):
                                if self.platform == KISS.PLATFORM_ESP32:
                                    if self.online:
                                        RNS.log("Detected reset while device was online, reinitialising device...", RNS.LOG_ERROR)
                                        raise IOError("ESP32 reset")
                        elif (command == KISS.CMD_READY):
                            self.process_queue()
                        elif (command == KISS.CMD_DETECT):
                            if byte == KISS.DETECT_RESP:
                                self.detected = True
                            else:
                                self.detected = False
                        elif (command == KISS.CMD_INTERFACES):
                            command_buffer = command_buffer+bytes([byte])
                            if (len(command_buffer) == 2):
                                # add the interface to the back of the list, they're all given from vport 0 and up in order
                                self.subinterface_types.append(KISS.interface_type_to_str(command_buffer[1]))
                                command_buffer = b""
                        
                else:
                    time_since_last = int(time.time()*1000) - last_read_ms
                    if len(data_buffer) > 0 and time_since_last > self.timeout:
                        RNS.log(str(self)+" serial read timeout in command "+str(command), RNS.LOG_WARNING)
                        data_buffer = b""
                        in_frame = False
                        command = KISS.CMD_UNKNOWN
                        escape = False

                    if self.id_interval != None and self.id_callsign != None:
                        if self.first_tx != None:
                            if time.time() > self.first_tx + self.id_interval:
                                interface_available = False
                                for interface in self.subinterfaces:
                                    if interface != 0 and interface.online:
                                        interface_available = True
                                        self.subinterfaces[interface.index].processOutgoing(self.id_callsign)

                                if interface_available:
                                    RNS.log("Interface "+str(self)+" is transmitting beacon data on all subinterfaces: "+str(self.id_callsign.decode("utf-8")), RNS.LOG_DEBUG)

                    sleep(0.08)

        except Exception as e:
            self.online = False
            RNS.log("A serial port error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is now offline.", RNS.LOG_ERROR)

            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)

            self.teardown_subinterfaces()

        self.online = False
        try:
            self.serial.close()
        except Exception as e:
            pass

        if not self.detached and not self.reconnecting:
            self.reconnect_port()

    def reconnect_port(self):
        self.reconnecting = True
        while not self.online and not self.detached:
            try:
                time.sleep(5)
                RNS.log("Attempting to reconnect serial port "+str(self.port)+" for "+str(self)+"...", RNS.LOG_VERBOSE)
                self.open_port()
                if self.serial.is_open:
                    self.configure_device()
            except Exception as e:
                RNS.log("Error while reconnecting port, the contained exception was: "+str(e), RNS.LOG_ERROR)

        self.reconnecting = False
        if self.online:
            RNS.log("Reconnected serial port for "+str(self))

    def detach(self):
        self.detached = True
        self.disable_external_framebuffer()

        for interface in self.subinterfaces:
            if interface != 0:
                self.setRadioState(KISS.RADIO_STATE_OFF, interface)
        self.leave()

    def teardown_subinterfaces(self):
        for interface in self.subinterfaces:
            if interface != 0:
                if interface in RNS.Transport.interfaces:
                    RNS.Transport.interfaces.remove(interface)
                self.subinterfaces[interface.index] = 0

    def should_ingress_limit(self):
        return False

    def process_queue(self):
        for interface in self.subinterfaces:
            if interface != 0:
                interface.process_queue()

    def __str__(self):
        return "RNodeMultiInterface["+str(self.name)+"]"

class RNodeSubInterface(Interface):
    LOW_FREQ_MIN = 137000000
    LOW_FREQ_MAX = 1000000000

    HIGH_FREQ_MIN = 2200000000
    HIGH_FREQ_MAX = 2600000000

    RSSI_OFFSET = 157

    Q_SNR_MIN_BASE = -9
    Q_SNR_MAX      = 6
    Q_SNR_STEP     = 2

    def __init__(self, owner, name, parent_interface, index, interface_type, frequency = None, bandwidth = None, txpower = None, sf = None, cr = None, flow_control = False, st_alock = None, lt_alock = None,):
        if RNS.vendor.platformutils.is_android():
            raise SystemError("Invalid interface type. The Android-specific RNode interface must be used on Android")

        import importlib
        if importlib.util.find_spec('serial') != None:
            import serial
        else:
            RNS.log("Using the RNode interface requires a serial communication module to be installed.", RNS.LOG_CRITICAL)
            RNS.log("You can install one with the command: python3 -m pip install pyserial", RNS.LOG_CRITICAL)
            RNS.panic()

        super().__init__()
        
        if index == 0:
            sel_cmd = KISS.CMD_SEL_INT0
            data_cmd= KISS.CMD_INT0_DATA
        elif index == 1:
            sel_cmd = KISS.CMD_SEL_INT1
            data_cmd= KISS.CMD_INT1_DATA
        elif index == 2:
            sel_cmd = KISS.CMD_SEL_INT2
            data_cmd= KISS.CMD_INT2_DATA
        elif index == 3:
            sel_cmd = KISS.CMD_SEL_INT3
            data_cmd= KISS.CMD_INT3_DATA
        elif index == 4:
            sel_cmd = KISS.CMD_SEL_INT4
            data_cmd= KISS.CMD_INT4_DATA
        elif index == 5:
            sel_cmd = KISS.CMD_SEL_INT5
            data_cmd= KISS.CMD_INT5_DATA
        elif index == 6:
            sel_cmd = KISS.CMD_SEL_INT6
            data_cmd= KISS.CMD_INT6_DATA
        elif index == 7:
            sel_cmd = KISS.CMD_SEL_INT7
            data_cmd= KISS.CMD_INT7_DATA
        elif index == 8:
            sel_cmd = KISS.CMD_SEL_INT8
            data_cmd= KISS.CMD_INT8_DATA
        elif index == 9:
            sel_cmd = KISS.CMD_SEL_INT9
            data_cmd= KISS.CMD_INT9_DATA
        elif index == 10:
            sel_cmd = KISS.CMD_SEL_INT10
            data_cmd= KISS.CMD_INT10_DATA
        elif index == 11:
            sel_cmd = KISS.CMD_SEL_INT11
            data_cmd= KISS.CMD_INT11_DATA
        else:
            sel_cmd = KISS.CMD_SEL_INT0
            data_cmd= KISS.CMD_INT0_DATA

        self.owner       = owner
        self.name        = name
        self.index       = index
        self.sel_cmd     = sel_cmd
        self.data_cmd    = data_cmd
        self.interface_type= interface_type
        self.flow_control= flow_control
        self.online      = False

        self.frequency   = frequency
        self.bandwidth   = bandwidth
        self.txpower     = txpower
        self.sf          = sf
        self.cr          = cr
        self.state       = KISS.RADIO_STATE_OFF
        self.bitrate     = 0
        self.st_alock    = st_alock
        self.lt_alock    = lt_alock
        self.platform    = None
        self.display     = None
        self.mcu         = None

        self.r_frequency = None
        self.r_bandwidth = None
        self.r_txpower   = None
        self.r_sf        = None
        self.r_cr        = None
        self.r_state     = None
        self.r_lock      = None
        self.r_stat_rx   = None
        self.r_stat_tx   = None
        self.r_stat_rssi = None
        self.r_stat_snr  = None
        self.r_st_alock  = None
        self.r_lt_alock  = None
        self.r_airtime_short      = 0.0
        self.r_airtime_long       = 0.0
        self.r_channel_load_short = 0.0
        self.r_channel_load_long  = 0.0
        self.r_symbol_time_ms = None
        self.r_symbol_rate = None
        self.r_preamble_symbols = None
        self.r_premable_time_ms = None

        self.packet_queue    = []
        self.interface_ready = False
        self.parent_interface = parent_interface
        self.announce_rate_target = None

        self.mode = None
        self.announce_cap = None
        self.bitrate = None
        self.ifac_size = None

        # add this interface to the subinterfaces array
        self.parent_interface.subinterfaces[index] = self

        self.validcfg  = True
        if (self.interface_type == "SX126X" or self.interface_type == "SX127X"):
            if (self.frequency < RNodeSubInterface.LOW_FREQ_MIN or self.frequency > RNodeSubInterface.LOW_FREQ_MAX):
                RNS.log("Invalid frequency configured for "+str(self), RNS.LOG_ERROR)
                self.validcfg = False
        elif (self.interface_type == "SX128X"):
            if (self.frequency < RNodeSubInterface.HIGH_FREQ_MIN or self.frequency > RNodeSubInterface.HIGH_FREQ_MAX):
                RNS.log("Invalid frequency configured for "+str(self), RNS.LOG_ERROR)
                self.validcfg = False
        else:
            RNS.log("Invalid interface type configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.txpower < -9 or self.txpower > 27):
            RNS.log("Invalid TX power configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.bandwidth < 7800 or self.bandwidth > 1625000):
            RNS.log("Invalid bandwidth configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.sf < 5 or self.sf > 12):
            RNS.log("Invalid spreading factor configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.cr < 5 or self.cr > 8):
            RNS.log("Invalid coding rate configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.st_alock and (self.st_alock < 0.0 or self.st_alock > 100.0)):
            RNS.log("Invalid short-term airtime limit configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.lt_alock and (self.lt_alock < 0.0 or self.lt_alock > 100.0)):
            RNS.log("Invalid long-term airtime limit configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (not self.validcfg):
            raise ValueError("The configuration for "+str(self)+" contains errors, interface is offline")

        self.configure_device()

    def configure_device(self):
        self.r_frequency = None
        self.r_bandwidth = None
        self.r_txpower   = None
        self.r_sf        = None
        self.r_cr        = None
        self.r_state     = None
        self.r_lock      = None
        sleep(2.0)

        RNS.log("Configuring RNode subinterface "+str(self)+"...", RNS.LOG_VERBOSE)
        self.initRadio()
        if (self.validateRadioState()):
            self.interface_ready = True
            RNS.log(str(self)+" is configured and powered up")
            sleep(0.3)
            self.online = True
        else:
            RNS.log("After configuring "+str(self)+", the reported radio parameters did not match your configuration.", RNS.LOG_ERROR)
            RNS.log("Make sure that your hardware actually supports the parameters specified in the configuration", RNS.LOG_ERROR)
            RNS.log("Aborting RNode startup", RNS.LOG_ERROR)
            

    def initRadio(self):
        self.parent_interface.setFrequency(self.frequency, self)
        self.parent_interface.setBandwidth(self.bandwidth, self)
        self.parent_interface.setTXPower(self.txpower, self)
        self.parent_interface.setSpreadingFactor(self.sf, self)
        self.parent_interface.setCodingRate(self.cr, self)
        self.parent_interface.setSTALock(self.st_alock, self)
        self.parent_interface.setLTALock(self.lt_alock, self)
        self.parent_interface.setRadioState(KISS.RADIO_STATE_ON, self)
        self.state = KISS.RADIO_STATE_ON

    def validateRadioState(self):
        RNS.log("Waiting for radio configuration validation for "+str(self)+"...", RNS.LOG_VERBOSE)
        sleep(0.25);

        self.validcfg = True
        if (self.r_frequency != None and abs(self.frequency - int(self.r_frequency)) > 100):
            RNS.log("Frequency mismatch", RNS.LOG_ERROR)
            self.validcfg = False
        if (self.bandwidth != self.r_bandwidth):
            RNS.log("Bandwidth mismatch", RNS.LOG_ERROR)
            self.validcfg = False
        if (self.txpower != self.r_txpower):
            RNS.log("TX power mismatch", RNS.LOG_ERROR)
            self.validcfg = False
        if (self.sf != self.r_sf):
            RNS.log("Spreading factor mismatch", RNS.LOG_ERROR)
            self.validcfg = False
        if (self.state != self.r_state):
            RNS.log("Radio state mismatch", RNS.LOG_ERROR)
            self.validcfg = False

        if (self.validcfg):
            return True
        else:
            return False


    def updateBitrate(self):
        try:
            self.bitrate = self.r_sf * ( (4.0/self.r_cr) / (math.pow(2,self.r_sf)/(self.r_bandwidth/1000)) ) * 1000
            self.bitrate_kbps = round(self.bitrate/1000.0, 2)
            RNS.log(str(self)+" On-air bitrate is now "+str(self.bitrate_kbps)+ " kbps", RNS.LOG_VERBOSE)
        except:
            self.bitrate = 0

    def processIncoming(self, data):
        self.rxb += len(data)
        self.owner.inbound(data, self)
        self.r_stat_rssi = None
        self.r_stat_snr = None

    def processOutgoing(self,data):
        if self.online:
            if self.interface_ready:
                if self.flow_control:
                    self.interface_ready = False

                if data == self.parent_interface.id_callsign:
                    self.parent_interface.first_tx = None
                else:
                    if self.parent_interface.first_tx == None:
                        self.parent_interface.first_tx = time.time()
                self.txb += len(data)
                self.parent_interface.processOutgoing(data, self)
            else:
                self.queue(data)

    def queue(self, data):
        self.packet_queue.append(data)


    def process_queue(self):
        if len(self.packet_queue) > 0:
            data = self.packet_queue.pop(0)
            self.interface_ready = True
            self.processOutgoing(data)
        elif len(self.packet_queue) == 0:
            self.interface_ready = True

    def __str__(self):
        return self.parent_interface.name+"["+self.name+"]"
