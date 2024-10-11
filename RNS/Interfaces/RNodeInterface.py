# MIT License
#
# Copyright (c) 2016-2023 Mark Qvist / unsigned.io
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
    CMD_DATA        = 0x00
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
    CMD_STAT_BAT    = 0x27
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

    DETECT_REQ      = 0x73
    DETECT_RESP     = 0x46
    
    RADIO_STATE_OFF = 0x00
    RADIO_STATE_ON  = 0x01
    RADIO_STATE_ASK = 0xFF
    
    CMD_ERROR           = 0x90
    ERROR_INITRADIO     = 0x01
    ERROR_TXFAILED      = 0x02
    ERROR_EEPROM_LOCKED = 0x03
    ERROR_QUEUE_FULL    = 0x04
    ERROR_MEMORY_LOW    = 0x05
    ERROR_MODEM_TIMEOUT = 0x06

    PLATFORM_AVR   = 0x90
    PLATFORM_ESP32 = 0x80
    PLATFORM_NRF52 = 0x70

    @staticmethod
    def escape(data):
        data = data.replace(bytes([0xdb]), bytes([0xdb, 0xdd]))
        data = data.replace(bytes([0xc0]), bytes([0xdb, 0xdc]))
        return data
    

class RNodeInterface(Interface):
    MAX_CHUNK = 32768

    FREQ_MIN = 137000000
    FREQ_MAX = 3000000000

    RSSI_OFFSET = 157

    CALLSIGN_MAX_LEN    = 32

    REQUIRED_FW_VER_MAJ = 1
    REQUIRED_FW_VER_MIN = 52

    RECONNECT_WAIT = 5

    Q_SNR_MIN_BASE = -9
    Q_SNR_MAX      = 6
    Q_SNR_STEP     = 2

    BATTERY_STATE_UNKNOWN     = 0x00
    BATTERY_STATE_DISCHARGING = 0x01
    BATTERY_STATE_CHARGING    = 0x02
    BATTERY_STATE_CHARGED     = 0x03

    def __init__(self, owner, name, port, frequency = None, bandwidth = None, txpower = None, sf = None, cr = None, flow_control = False, id_interval = None, id_callsign = None, st_alock = None, lt_alock = None, ble_addr = None, ble_name = None, force_ble=False):
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
        
        self.pyserial    = serial
        self.serial      = None
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

        self.use_ble     = False
        self.ble_name    = ble_name
        self.ble_addr    = ble_addr
        self.ble         = None
        self.ble_rx_lock = threading.Lock()
        self.ble_tx_lock = threading.Lock()
        self.ble_rx_queue= b""
        self.ble_tx_queue= b""

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
        self.detected    = False
        self.firmware_ok = False
        self.maj_version = 0
        self.min_version = 0

        self.last_id     = 0
        self.first_tx    = None
        self.reconnect_w = RNodeInterface.RECONNECT_WAIT

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
        self.r_random    = None
        self.r_airtime_short      = 0.0
        self.r_airtime_long       = 0.0
        self.r_channel_load_short = 0.0
        self.r_channel_load_long  = 0.0
        self.r_symbol_time_ms = None
        self.r_symbol_rate = None
        self.r_preamble_symbols = None
        self.r_premable_time_ms = None
        self.r_battery_state = RNodeInterface.BATTERY_STATE_UNKNOWN
        self.r_battery_percent = 0

        self.packet_queue    = []
        self.flow_control    = flow_control
        self.interface_ready = False
        self.announce_rate_target = None

        if force_ble or self.ble_addr != None or self.ble_name != None:
            self.use_ble = True

        self.validcfg  = True
        if (self.frequency < RNodeInterface.FREQ_MIN or self.frequency > RNodeInterface.FREQ_MAX):
            RNS.log("Invalid frequency configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.txpower < 0 or self.txpower > 22):
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

        if id_interval != None and id_callsign != None:
            if (len(id_callsign.encode("utf-8")) <= RNodeInterface.CALLSIGN_MAX_LEN):
                self.should_id = True
                self.id_callsign = id_callsign.encode("utf-8")
                self.id_interval = id_interval
            else:
                RNS.log("The encoded ID callsign for "+str(self)+" exceeds the max length of "+str(RNodeInterface.CALLSIGN_MAX_LEN)+" bytes.", RNS.LOG_ERROR)
                self.validcfg = False
        else:
            self.id_interval = None
            self.id_callsign = None

        if (not self.validcfg):
            raise ValueError("The configuration for "+str(self)+" contains errors, interface is offline")

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
        if not self.use_ble:
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
        
        else:
            RNS.log(f"Opening BLE connection for {self}...")
            if self.ble != None and self.ble.running == False:
                self.ble.close()
                self.ble.cleanup()
                self.ble = None

            if self.ble == None:
                self.ble = BLEConnection(owner=self, target_name=self.ble_name, target_bt_addr=self.ble_addr)
                self.serial = self.ble

            open_time = time.time()
            while not self.ble.connected and time.time() < open_time + self.ble.CONNECT_TIMEOUT:
                time.sleep(1)

    def reset_radio_state(self):
        self.r_frequency = None
        self.r_bandwidth = None
        self.r_txpower   = None
        self.r_sf        = None
        self.r_cr        = None
        self.r_state     = None
        self.r_lock      = None
        self.detected    = False

    def configure_device(self):
        self.reset_radio_state()
        sleep(2.0)

        thread = threading.Thread(target=self.readLoop)
        thread.daemon = True
        thread.start()

        self.detect()
        if not self.use_ble:
            sleep(0.2)
        else:
            ble_detect_timeout = 5
            detect_time = time.time()
            while not self.detected and time.time() < detect_time + ble_detect_timeout:
                time.sleep(0.1)
            if self.detected:
                detect_time = RNS.prettytime(time.time()-detect_time)
            else:
                RNS.log(f"RNode detect timed out over {self.port}", RNS.LOG_ERROR)
        
        if not self.detected:
            RNS.log("Could not detect device for "+str(self), RNS.LOG_ERROR)
            self.serial.close()
        else:
            if self.platform == KISS.PLATFORM_ESP32 or self.platform == KISS.PLATFORM_NRF52:
                self.display = True

        RNS.log("Serial port "+self.port+" is now open")
        RNS.log("Configuring RNode interface...", RNS.LOG_VERBOSE)
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
            self.serial.close()
            

    def initRadio(self):
        self.setFrequency()
        self.setBandwidth()
        self.setTXPower()
        self.setSpreadingFactor()
        self.setCodingRate()
        self.setSTALock()
        self.setLTALock()
        self.setRadioState(KISS.RADIO_STATE_ON)

        if self.use_ble:
            time.sleep(2)

    def detect(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_DETECT, KISS.DETECT_REQ, KISS.FEND, KISS.CMD_FW_VERSION, 0x00, KISS.FEND, KISS.CMD_PLATFORM, 0x00, KISS.FEND, KISS.CMD_MCU, 0x00, KISS.FEND])
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
                line_start = line*RNodeInterface.FB_BYTES_PER_LINE
                line_end   = line_start+RNodeInterface.FB_BYTES_PER_LINE
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

    def setFrequency(self):
        c1 = self.frequency >> 24
        c2 = self.frequency >> 16 & 0xFF
        c3 = self.frequency >> 8 & 0xFF
        c4 = self.frequency & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_FREQUENCY])+data+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring frequency for "+str(self))

    def setBandwidth(self):
        c1 = self.bandwidth >> 24
        c2 = self.bandwidth >> 16 & 0xFF
        c3 = self.bandwidth >> 8 & 0xFF
        c4 = self.bandwidth & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_BANDWIDTH])+data+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring bandwidth for "+str(self))

    def setTXPower(self):
        txp = bytes([self.txpower])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_TXPOWER])+txp+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring TX power for "+str(self))

    def setSpreadingFactor(self):
        sf = bytes([self.sf])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_SF])+sf+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring spreading factor for "+str(self))

    def setCodingRate(self):
        cr = bytes([self.cr])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_CR])+cr+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring coding rate for "+str(self))

    def setSTALock(self):
        if self.st_alock != None:
            at = int(self.st_alock*100)
            c1 = at >> 8 & 0xFF
            c2 = at & 0xFF
            data = KISS.escape(bytes([c1])+bytes([c2]))

            kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_ST_ALOCK])+data+bytes([KISS.FEND])
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while configuring short-term airtime limit for "+str(self))

    def setLTALock(self):
        if self.lt_alock != None:
            at = int(self.lt_alock*100)
            c1 = at >> 8 & 0xFF
            c2 = at & 0xFF
            data = KISS.escape(bytes([c1])+bytes([c2]))

            kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_LT_ALOCK])+data+bytes([KISS.FEND])
            written = self.serial.write(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while configuring long-term airtime limit for "+str(self))

    def setRadioState(self, state):
        self.state = state
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_RADIO_STATE])+bytes([state])+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring radio state for "+str(self))

    def validate_firmware(self):
        if (self.maj_version > RNodeInterface.REQUIRED_FW_VER_MAJ):
            self.firmware_ok = True
        else:
            if (self.maj_version >= RNodeInterface.REQUIRED_FW_VER_MAJ):
                if (self.min_version >= RNodeInterface.REQUIRED_FW_VER_MIN):
                    self.firmware_ok = True
        
        if self.firmware_ok:
            return

        RNS.log("The firmware version of the connected RNode is "+str(self.maj_version)+"."+str(self.min_version), RNS.LOG_ERROR)
        RNS.log("This version of Reticulum requires at least version "+str(RNodeInterface.REQUIRED_FW_VER_MAJ)+"."+str(RNodeInterface.REQUIRED_FW_VER_MIN), RNS.LOG_ERROR)
        RNS.log("Please update your RNode firmware with rnodeconf from https://github.com/markqvist/rnodeconfigutil/")
        RNS.panic()


    def validateRadioState(self):
        RNS.log("Waiting for radio configuration validation for "+str(self)+"...", RNS.LOG_VERBOSE)
        if self.use_ble:
            sleep(1.00)
        else:
            sleep(0.25)

        if self.use_ble and self.ble != None and self.ble.device_disappeared:
            RNS.log(f"Device disappeared during radio state validation for {self}", RNS.LOG_ERROR)
            return False

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
        datalen = len(data)
        if self.online:
            if self.interface_ready:
                if self.flow_control:
                    self.interface_ready = False

                if data == self.id_callsign:
                    self.first_tx = None
                else:
                    if self.first_tx == None:
                        self.first_tx = time.time()

                data    = KISS.escape(data)
                frame   = bytes([0xc0])+bytes([0x00])+data+bytes([0xc0])

                written = self.serial.write(frame)
                self.txb += datalen

                if written != len(frame):
                    raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))
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

                    if (in_frame and byte == KISS.FEND and command == KISS.CMD_DATA):
                        in_frame = False
                        self.processIncoming(data_buffer)
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
                        elif (command == KISS.CMD_DATA):
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
                                    self.r_frequency = command_buffer[0] << 24 | command_buffer[1] << 16 | command_buffer[2] << 8 | command_buffer[3]
                                    RNS.log(str(self)+" Radio reporting frequency is "+str(self.r_frequency/1000000.0)+" MHz", RNS.LOG_DEBUG)
                                    self.updateBitrate()

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
                                    self.r_bandwidth = command_buffer[0] << 24 | command_buffer[1] << 16 | command_buffer[2] << 8 | command_buffer[3]
                                    RNS.log(str(self)+" Radio reporting bandwidth is "+str(self.r_bandwidth/1000.0)+" KHz", RNS.LOG_DEBUG)
                                    self.updateBitrate()

                        elif (command == KISS.CMD_TXPOWER):
                            self.r_txpower = byte
                            RNS.log(str(self)+" Radio reporting TX power is "+str(self.r_txpower)+" dBm", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_SF):
                            self.r_sf = byte
                            RNS.log(str(self)+" Radio reporting spreading factor is "+str(self.r_sf), RNS.LOG_DEBUG)
                            self.updateBitrate()
                        elif (command == KISS.CMD_CR):
                            self.r_cr = byte
                            RNS.log(str(self)+" Radio reporting coding rate is "+str(self.r_cr), RNS.LOG_DEBUG)
                            self.updateBitrate()
                        elif (command == KISS.CMD_RADIO_STATE):
                            self.r_state = byte
                            if self.r_state:
                                pass
                            else:
                                RNS.log(str(self)+" Radio reporting state is offline", RNS.LOG_DEBUG)

                        elif (command == KISS.CMD_RADIO_LOCK):
                            self.r_lock = byte
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

                        elif (command == KISS.CMD_STAT_RX):
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
                                    self.r_stat_rx = ord(command_buffer[0]) << 24 | ord(command_buffer[1]) << 16 | ord(command_buffer[2]) << 8 | ord(command_buffer[3])

                        elif (command == KISS.CMD_STAT_TX):
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
                                    self.r_stat_tx = ord(command_buffer[0]) << 24 | ord(command_buffer[1]) << 16 | ord(command_buffer[2]) << 8 | ord(command_buffer[3])

                        elif (command == KISS.CMD_STAT_RSSI):
                            self.r_stat_rssi = byte-RNodeInterface.RSSI_OFFSET
                        elif (command == KISS.CMD_STAT_SNR):
                            self.r_stat_snr = int.from_bytes(bytes([byte]), byteorder="big", signed=True) * 0.25
                            try:
                                sfs = self.r_sf-7
                                snr = self.r_stat_snr
                                q_snr_min = RNodeInterface.Q_SNR_MIN_BASE-sfs*RNodeInterface.Q_SNR_STEP
                                q_snr_max = RNodeInterface.Q_SNR_MAX
                                q_snr_span = q_snr_max-q_snr_min
                                quality = round(((snr-q_snr_min)/(q_snr_span))*100,1)
                                if quality > 100.0: quality = 100.0
                                if quality < 0.0: quality = 0.0
                                self.r_stat_q = quality
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
                                    self.r_st_alock = at/100.0
                                    RNS.log(str(self)+" Radio reporting short-term airtime limit is "+str(self.r_st_alock)+"%", RNS.LOG_DEBUG)
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
                                    self.r_lt_alock = at/100.0
                                    RNS.log(str(self)+" Radio reporting long-term airtime limit is "+str(self.r_lt_alock)+"%", RNS.LOG_DEBUG)
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

                                    if lst != self.r_symbol_time_ms or lsr != self.r_symbol_rate or prs != self.r_preamble_symbols or prt != self.r_premable_time_ms or cst != self.r_csma_slot_time_ms:
                                        self.r_symbol_time_ms    = lst
                                        self.r_symbol_rate       = lsr
                                        self.r_preamble_symbols  = prs
                                        self.r_premable_time_ms  = prt
                                        self.r_csma_slot_time_ms = cst
                                        RNS.log(str(self)+" Radio reporting symbol time is "+str(round(self.r_symbol_time_ms,2))+"ms (at "+str(self.r_symbol_rate)+" baud)", RNS.LOG_DEBUG)
                                        RNS.log(str(self)+" Radio reporting preamble is "+str(self.r_preamble_symbols)+" symbols ("+str(self.r_premable_time_ms)+"ms)", RNS.LOG_DEBUG)
                                        RNS.log(str(self)+" Radio reporting CSMA slot time is "+str(self.r_csma_slot_time_ms)+"ms", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_STAT_BAT):
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
                                    bat_percent = command_buffer[1]
                                    if bat_percent > 100:
                                        bat_percent = 100
                                    if bat_percent < 0:
                                        bat_percent = 0
                                    self.r_battery_state   = command_buffer[0]
                                    self.r_battery_percent = bat_percent
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
                            elif (byte == KISS.ERROR_MEMORY_LOW):
                                RNS.log(str(self)+" hardware error (code "+RNS.hexrep(byte)+"): Memory exhausted", RNS.LOG_ERROR)
                                self.hw_errors.append({"error": KISS.ERROR_MEMORY_LOW, "description": "Memory exhausted on connected device"})
                            elif (byte == KISS.ERROR_MODEM_TIMEOUT):
                                RNS.log(str(self)+" hardware error (code "+RNS.hexrep(byte)+"): Modem communication timed out", RNS.LOG_ERROR)
                                self.hw_errors.append({"error": KISS.ERROR_MODEM_TIMEOUT, "description": "Modem communication timed out on connected device"})
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
                                RNS.log("Interface "+str(self)+" is transmitting beacon data: "+str(self.id_callsign.decode("utf-8")), RNS.LOG_DEBUG)
                                self.processOutgoing(self.id_callsign)

                    sleep(0.08)

        except Exception as e:
            self.online = False
            RNS.log("A serial port error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is now offline.", RNS.LOG_ERROR)

            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)

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
        self.setRadioState(KISS.RADIO_STATE_OFF)
        self.leave()
        
        if self.use_ble:
            self.ble.close()

    def should_ingress_limit(self):
        return False

    def get_battery_state(self):
        return self.r_battery_state

    def get_battery_state_string(self):
        if self.r_battery_state == RNodeInterface.BATTERY_STATE_CHARGED:
            return "charged"
        elif  self.r_battery_state == RNodeInterface.BATTERY_STATE_CHARGING:
            return "charging"
        elif self.r_battery_state == RNodeInterface.BATTERY_STATE_DISCHARGING:
            return "discharging"
        else:
            return "unknown"

    def get_battery_percent(self):
        return self.r_battery_percent

    def ble_receive(self, data):
        with self.ble_rx_lock:
            self.ble_rx_queue += data

    def ble_waiting(self):
        return len(self.ble_tx_queue) > 0

    def get_ble_waiting(self, n):
        with self.ble_tx_lock:
            data = self.ble_tx_queue[:n]
            self.ble_tx_queue = self.ble_tx_queue[n:]
            return data

    def __str__(self):
        return "RNodeInterface["+str(self.name)+"]"

class BLEConnection():
    UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
    bleak = None

    SCAN_TIMEOUT = 2.0
    CONNECT_TIMEOUT = 5.0

    @property
    def is_open(self):
        return self.connected

    @property
    def in_waiting(self):
        buflen = len(self.owner.ble_rx_queue)
        return buflen > 0

    def write(self, data_bytes):
        with self.owner.ble_tx_lock:
            self.owner.ble_tx_queue += data_bytes
            return len(data_bytes)

    def read(self, n):
        with self.owner.ble_rx_lock:
            data = self.owner.ble_rx_queue[:n]
            self.owner.ble_rx_queue = self.owner.ble_rx_queue[n:]
            return data

    def close(self):
        if self.connected and self.ble_device:
            RNS.log(f"Disconnecting BLE device from {self.owner}", RNS.LOG_DEBUG)
            self.must_disconnect = True

            while self.connect_job_running:
                time.sleep(0.1)

    def __init__(self, owner=None, target_name=None, target_bt_addr=None):
        self.owner = owner
        self.target_name = target_name
        self.target_bt_addr = target_bt_addr
        self.scan_timeout = BLEConnection.SCAN_TIMEOUT
        self.ble_device = None
        self.last_client = None
        self.connected = False
        self.running = False
        self.should_run = False
        self.must_disconnect = False
        self.connect_job_running = False
        self.device_disappeared = False

        import importlib
        if BLEConnection.bleak == None:
            if importlib.util.find_spec("bleak") != None:
                import bleak
                BLEConnection.bleak = bleak
                
                import asyncio
                BLEConnection.asyncio = asyncio
            else:
                RNS.log("Using the RNode interface over BLE requires a the \"bleak\" module to be installed.", RNS.LOG_CRITICAL)
                RNS.log("You can install one with the command: python3 -m pip install bleak", RNS.LOG_CRITICAL)
                RNS.panic()

        self.should_run = True
        self.connection_thread = threading.Thread(target=self.connection_job, daemon=True).start()

    def cleanup(self):
        try:
            if self.last_client != None:
                self.asyncio.run(self.last_client.disconnect())
        except Exception as e:
            RNS.log(f"Error while disconnecting BLE device on cleanup for {self.owner}", RNS.LOG_ERROR)

        self.should_run = False

    def connection_job(self):
        while self.should_run:
            if self.ble_device == None:
                self.ble_device = self.find_target_device()

            if type(self.ble_device) == self.bleak.backends.device.BLEDevice:
                if not self.connected:
                    self.connect_device()

            time.sleep(1)

        self.cleanup()
        self.running = False
        RNS.log(f"BLE connection job for {self.owner} ended", RNS.LOG_DEBUG)

    def connect_device(self):
        if self.ble_device != None and type(self.ble_device) == self.bleak.backends.device.BLEDevice:
            RNS.log(f"Connecting BLE device {self.ble_device} for {self.owner}...", RNS.LOG_DEBUG)

            async def connect_job():
                self.connect_job_running = True
                async with self.bleak.BleakClient(self.ble_device, disconnected_callback=self.device_disconnected) as ble_client:
                    def handle_rx(device, data):
                        if self.owner != None:
                            self.owner.ble_receive(data)

                    self.connected = True
                    self.ble_device = ble_client
                    self.last_client = ble_client
                    self.owner.port = str(f"ble://{ble_client.address}")

                    loop = self.asyncio.get_running_loop()
                    uart_service = ble_client.services.get_service(BLEConnection.UART_SERVICE_UUID)
                    rx_characteristic = uart_service.get_characteristic(BLEConnection.UART_RX_CHAR_UUID)
                    await ble_client.start_notify(BLEConnection.UART_TX_CHAR_UUID, handle_rx)

                    while self.connected:
                        if self.owner != None and self.owner.ble_waiting():
                            outbound_data = self.owner.get_ble_waiting(rx_characteristic.max_write_without_response_size)
                            await ble_client.write_gatt_char(rx_characteristic, outbound_data, response=False)
                        elif self.must_disconnect:
                            await ble_client.disconnect()
                        else:
                            await self.asyncio.sleep(0.1)


            try:
                self.asyncio.run(connect_job())
            except Exception as e:
                RNS.log(f"Could not connect BLE device {self.ble_device} for {self.owner}. Possibly missing authentication.", RNS.LOG_ERROR)

            self.connect_job_running = False

    def device_disconnected(self, device):
        RNS.log(f"BLE device for {self.owner} disconnected", RNS.LOG_NOTICE)
        self.connected = False
        self.ble_device = None
        self.device_disappeared = True

    def find_target_device(self):
        RNS.log(f"Searching for attachable BLE device for {self.owner}...", RNS.LOG_EXTREME)
        def device_filter(device: self.bleak.backends.device.BLEDevice, adv: self.bleak.backends.scanner.AdvertisementData):
            if BLEConnection.UART_SERVICE_UUID.lower() in adv.service_uuids:
                if self.device_bonded(device):
                    if self.target_bt_addr == None and self.target_name == None:
                        if device.name.startswith("RNode "):
                            return True

                    if self.target_bt_addr == None or (device.address != None and device.address == self.target_bt_addr):
                        if self.target_name == None or (device.name != None and device.name == self.target_name):
                            return True

                else:
                    if self.target_bt_addr != None and device.address == self.target_bt_addr:
                        RNS.log(f"Can't connect to target device {self.target_bt_addr} over BLE, device is not bonded", RNS.LOG_ERROR)
                    
                    elif self.target_name != None and device.name == self.target_name:
                        RNS.log(f"Can't connect to target device {self.target_name} over BLE, device is not bonded", RNS.LOG_ERROR)

            return False

        device = None
        try:
            device = self.asyncio.run(self.bleak.BleakScanner.find_device_by_filter(device_filter, timeout=self.scan_timeout))
        except Exception as e:
            RNS.log(f"Error while finding BLE device for {self.owner}: {e}", RNS.LOG_ERROR)
            self.should_run = False

        return device

    def device_bonded(self, device):
        try:
            if hasattr(device, "details"):
                if "props" in device.details and "Bonded" in device.details["props"]:
                    if device.details["props"]["Bonded"] == True:
                        return True
        
        except Exception as e:
            RNS.log(f"Error while determining device bond status for {device}, the contained exception was: {e}", RNS.LOG_ERROR)

        return False
