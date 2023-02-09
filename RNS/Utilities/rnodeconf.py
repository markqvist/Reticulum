#!python3

# MIT License
#
# Copyright (c) 2018-2022 Mark Qvist - unsigned.io/rnode
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

from time import sleep
import argparse
import threading
import os
import os.path
import struct
import datetime
import time
import math
import hashlib
from urllib.request import urlretrieve
from importlib import util
import RNS

RNS.logtimefmt      = "%H:%M:%S"
RNS.compact_log_fmt = True

program_version = "2.1.0"
eth_addr = "0x81F7B979fEa6134bA9FD5c701b3501A2e61E897a"
btc_addr = "3CPmacGm34qYvR6XWLVEJmi2aNe3PZqUuq"
xmr_addr = "87HcDx6jRSkMQ9nPRd5K9hGGpZLn2s7vWETjMaVM5KfV4TD36NcYa8J8WSxhTSvBzzFpqDwp2fg5GX2moZ7VAP9QMZCZGET"

rnode = None
rnode_serial = None
rnode_port = None
rnode_baudrate = 115200
known_keys = [["unsigned.io", "30819f300d06092a864886f70d010101050003818d0030818902818100bf831ebd99f43b477caf1a094bec829389da40653e8f1f83fc14bf1b98a3e1cc70e759c213a43f71e5a47eb56a9ca487f241335b3e6ff7cdde0ee0a1c75c698574aeba0485726b6a9dfc046b4188e3520271ee8555a8f405cf21f81f2575771d0b0887adea5dd53c1f594f72c66b5f14904ffc2e72206a6698a490d51ba1105b0203010001"], ["unsigned.io", "30819f300d06092a864886f70d010101050003818d0030818902818100e5d46084e445595376bf7efd9c6ccf19d39abbc59afdb763207e4ff68b8d00ebffb63847aa2fe6dd10783d3ea63b55ac66f71ad885c20e223709f0d51ed5c6c0d0b093be9e1d165bb8a483a548b67a3f7a1e4580f50e75b306593fa6067ae259d3e297717bd7ff8c8f5b07f2bed89929a9a0321026cf3699524db98e2d18fb2d020300ff39"]]
firmware_update_url = "https://github.com/markqvist/RNode_Firmware/releases/download/"
fw_filename = None
mapped_model = None

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
    CMD_DETECT      = 0x08
    CMD_LEAVE       = 0x0A
    CMD_READY       = 0x0F
    CMD_STAT_RX     = 0x21
    CMD_STAT_TX     = 0x22
    CMD_STAT_RSSI   = 0x23
    CMD_STAT_SNR    = 0x24
    CMD_BLINK       = 0x30
    CMD_RANDOM      = 0x40
    CMD_BT_CTRL     = 0x46
    CMD_BT_PIN      = 0x62
    CMD_BOARD       = 0x47
    CMD_PLATFORM    = 0x48
    CMD_MCU         = 0x49
    CMD_FW_VERSION  = 0x50
    CMD_ROM_READ    = 0x51
    CMD_ROM_WRITE   = 0x52
    CMD_ROM_WIPE    = 0x59
    CMD_CONF_SAVE   = 0x53
    CMD_CONF_DELETE = 0x54
    CMD_RESET       = 0x55
    CMD_DEV_HASH    = 0x56
    CMD_DEV_SIG     = 0x57
    CMD_HASHES      = 0x60
    CMD_FW_HASH     = 0x58
    CMD_FW_UPD      = 0x61

    DETECT_REQ      = 0x73
    DETECT_RESP     = 0x46
    
    RADIO_STATE_OFF = 0x00
    RADIO_STATE_ON  = 0x01
    RADIO_STATE_ASK = 0xFF
    
    CMD_ERROR           = 0x90
    ERROR_INITRADIO     = 0x01
    ERROR_TXFAILED      = 0x02
    ERROR_EEPROM_LOCKED = 0x03

    @staticmethod
    def escape(data):
        data = data.replace(bytes([0xdb]), bytes([0xdb, 0xdd]))
        data = data.replace(bytes([0xc0]), bytes([0xdb, 0xdc]))
        return data

class ROM():
    PLATFORM_AVR   = 0x90
    PLATFORM_ESP32 = 0x80

    MCU_1284P      = 0x91
    MCU_2560       = 0x92
    MCU_ESP32      = 0x81

    PRODUCT_RNODE  = 0x03
    MODEL_A4       = 0xA4
    MODEL_A9       = 0xA9
    MODEL_A3       = 0xA3
    MODEL_A8       = 0xA8
    MODEL_A2       = 0xA2
    MODEL_A7       = 0xA7

    PRODUCT_T32_20 = 0xB0
    MODEL_B3       = 0xB3
    MODEL_B8       = 0xB8

    PRODUCT_T32_21 = 0xB1
    MODEL_B4       = 0xB4
    MODEL_B9       = 0xB9

    PRODUCT_H32_V2 = 0xC0
    MODEL_C4       = 0xC4
    MODEL_C9       = 0xC9

    PRODUCT_TBEAM  = 0xE0
    MODEL_E4       = 0xE4
    MODEL_E9       = 0xE9
    
    PRODUCT_HMBRW  = 0xF0
    MODEL_FF       = 0xFF
    MODEL_FE       = 0xFE

    ADDR_PRODUCT   = 0x00
    ADDR_MODEL     = 0x01
    ADDR_HW_REV    = 0x02
    ADDR_SERIAL    = 0x03
    ADDR_MADE      = 0x07
    ADDR_CHKSUM    = 0x0B
    ADDR_SIGNATURE = 0x1B
    ADDR_INFO_LOCK = 0x9B
    ADDR_CONF_SF   = 0x9C
    ADDR_CONF_CR   = 0x9D
    ADDR_CONF_TXP  = 0x9E
    ADDR_CONF_BW   = 0x9F
    ADDR_CONF_FREQ = 0xA3
    ADDR_CONF_OK   = 0xA7

    INFO_LOCK_BYTE = 0x73
    CONF_OK_BYTE   = 0x73

    BOARD_RNODE         = 0x31
    BOARD_HMBRW         = 0x32
    BOARD_TBEAM         = 0x33
    BOARD_HUZZAH32      = 0x34
    BOARD_GENERIC_ESP32 = 0x35
    BOARD_LORA32_V2_0   = 0x36
    BOARD_LORA32_V2_1   = 0x37

mapped_product = ROM.PRODUCT_RNODE
products = {
    ROM.PRODUCT_RNODE:  "RNode",
    ROM.PRODUCT_HMBRW:  "Hombrew RNode",
    ROM.PRODUCT_TBEAM:  "LilyGO T-Beam",
    ROM.PRODUCT_T32_20: "LilyGO LoRa32 v2.0",
    ROM.PRODUCT_T32_21: "LilyGO LoRa32 v2.1",
    ROM.PRODUCT_H32_V2: "Heltec LoRa32 v2",
}

platforms = {
    ROM.PLATFORM_AVR: "AVR",
    ROM.PLATFORM_ESP32:"ESP32",
}

mcus = {
    ROM.MCU_1284P: "ATmega1284P",
    ROM.MCU_2560:"ATmega2560",
    ROM.MCU_ESP32:"Espressif Systems ESP32",
}

models = {
    0xA4: [410000000, 525000000, 14, "410 - 525 MHz", "rnode_firmware.hex"],
    0xA9: [820000000, 1020000000, 17, "820 - 1020 MHz", "rnode_firmware.hex"],
    0xA2: [410000000, 525000000, 17, "410 - 525 MHz", "rnode_firmware_ng21.zip"],
    0xA7: [820000000, 1020000000, 17, "820 - 1020 MHz", "rnode_firmware_ng21.zip"],
    0xA3: [410000000, 525000000, 17, "410 - 525 MHz", "rnode_firmware_ng20.zip"],
    0xA8: [820000000, 1020000000, 17, "820 - 1020 MHz", "rnode_firmware_ng20.zip"],
    0xB3: [420000000, 520000000, 17, "420 - 520 MHz", "rnode_firmware_lora32v20.zip"],
    0xB8: [850000000, 950000000, 17, "850 - 950 MHz", "rnode_firmware_lora32v20.zip"],
    0xB4: [420000000, 520000000, 17, "420 - 520 MHz", "rnode_firmware_lora32v21.zip"],
    0xB9: [850000000, 950000000, 17, "850 - 950 MHz", "rnode_firmware_lora32v21.zip"],
    0xC4: [420000000, 520000000, 17, "420 - 520 MHz", "rnode_firmware_heltec32v2.zip"],
    0xC9: [850000000, 950000000, 17, "850 - 950 MHz", "rnode_firmware_heltec32v2.zip"],
    0xE4: [420000000, 520000000, 17, "420 - 520 MHz", "rnode_firmware_tbeam.zip"],
    0xE9: [850000000, 950000000, 17, "850 - 950 MHz", "rnode_firmware_tbeam.zip"],
    0xFE: [100000000, 1100000000, 17, "(Band capabilities unknown)", None],
    0xFF: [100000000, 1100000000, 14, "(Band capabilities unknown)", None],
}

CNF_DIR = None
UPD_DIR = None
FWD_DIR = None
EXT_DIR = None

try:
    CNF_DIR = os.path.expanduser("~/.config/rnodeconf")
    UPD_DIR = CNF_DIR+"/update"
    FWD_DIR = CNF_DIR+"/firmware"
    EXT_DIR = CNF_DIR+"/extracted"
    RT_PATH = CNF_DIR+"/recovery_esptool.py"

    if not os.path.isdir(CNF_DIR):
        os.makedirs(CNF_DIR)
    if not os.path.isdir(UPD_DIR):
        os.makedirs(UPD_DIR)
    if not os.path.isdir(FWD_DIR):
        os.makedirs(FWD_DIR)
    if not os.path.isdir(EXT_DIR):
        os.makedirs(EXT_DIR)

except Exception as e:
    print("No access to directory "+str(CNF_DIR)+". This utility needs file system access to store firmware and data files. Cannot continue.")
    print("The contained exception was:")
    print(str(e))
    exit(99)

squashvw = False

class RNode():
    def __init__(self, serial_instance):
        self.serial = serial_instance
        self.timeout     = 100

        self.r_frequency = None
        self.r_bandwidth = None
        self.r_txpower   = None
        self.r_sf        = None
        self.r_state     = None
        self.r_lock      = None

        self.sf = None
        self.cr = None
        self.txpower = None
        self.frequency = None
        self.bandwidth = None

        self.detected = None

        self.platform = None
        self.mcu = None
        self.eeprom = None
        self.major_version = None
        self.minor_version = None
        self.version = None

        self.provisioned = None
        self.product = None
        self.board = None
        self.model = None
        self.hw_rev = None
        self.made = None
        self.serialno = None
        self.checksum = None
        self.device_hash = None
        self.firmware_hash = None
        self.signature = None
        self.signature_valid = False
        self.locally_signed = False
        self.vendor = None

        self.min_freq = None
        self.max_freq = None
        self.max_output = None

        self.configured = None
        self.conf_sf = None
        self.conf_cr = None
        self.conf_txpower = None
        self.conf_frequency = None
        self.conf_bandwidth = None

    def disconnect(self):
        self.leave()
        self.serial.close()

    def readLoop(self):
        try:
            in_frame = False
            escape = False
            command = KISS.CMD_UNKNOWN
            data_buffer = b""
            command_buffer = b""
            last_read_ms = int(time.time()*1000)

            while self.serial.is_open:
                try:
                    data_waiting = self.serial.in_waiting
                except Exception as e:
                    data_waiting = False

                if data_waiting:
                    byte = ord(self.serial.read(1))
                    last_read_ms = int(time.time()*1000)

                    if (in_frame and byte == KISS.FEND and command == KISS.CMD_ROM_READ):
                        self.eeprom = data_buffer
                        in_frame = False
                        data_buffer = b""
                        command_buffer = b""
                    elif (byte == KISS.FEND):
                        in_frame = True
                        command = KISS.CMD_UNKNOWN
                        data_buffer = b""
                        command_buffer = b""
                    elif (in_frame and len(data_buffer) < 512):
                        if (len(data_buffer) == 0 and command == KISS.CMD_UNKNOWN):
                            command = byte
                        elif (command == KISS.CMD_ROM_READ):
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
                                    RNS.log("Radio reporting frequency is "+str(self.r_frequency/1000000.0)+" MHz")
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
                                    RNS.log("Radio reporting bandwidth is "+str(self.r_bandwidth/1000.0)+" KHz")
                                    self.updateBitrate()

                        elif (command == KISS.CMD_BT_PIN):
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
                                    self.r_bt_pin = command_buffer[0] << 24 | command_buffer[1] << 16 | command_buffer[2] << 8 | command_buffer[3]
                                    RNS.log("Bluetooth pairing PIN is: {:06d}".format(self.r_bt_pin))

                        elif (command == KISS.CMD_DEV_HASH):
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
                                if (len(command_buffer) == 32):
                                    self.device_hash = command_buffer

                        elif (command == KISS.CMD_HASHES):
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
                                if (len(command_buffer) == 33):
                                    if command_buffer[0] == 0x02:
                                        self.firmware_hash = command_buffer[1:]

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
                                    self.major_version = command_buffer[0]
                                    self.minor_version = command_buffer[1]
                                    self.updateVersion()

                        elif (command == KISS.CMD_BOARD):
                            self.board = byte

                        elif (command == KISS.CMD_PLATFORM):
                            self.platform = byte

                        elif (command == KISS.CMD_MCU):
                            self.mcu = byte

                        elif (command == KISS.CMD_TXPOWER):
                            self.r_txpower = byte
                            RNS.log("Radio reporting TX power is "+str(self.r_txpower)+" dBm")
                        elif (command == KISS.CMD_SF):
                            self.r_sf = byte
                            RNS.log("Radio reporting spreading factor is "+str(self.r_sf))
                            self.updateBitrate()
                        elif (command == KISS.CMD_CR):
                            self.r_cr = byte
                            RNS.log("Radio reporting coding rate is "+str(self.r_cr))
                            self.updateBitrate()
                        elif (command == KISS.CMD_RADIO_STATE):
                            self.r_state = byte
                        elif (command == KISS.CMD_RADIO_LOCK):
                            self.r_lock = byte
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
                        elif (command == KISS.CMD_RANDOM):
                            self.r_random = byte
                        elif (command == KISS.CMD_ERROR):
                            if (byte == KISS.ERROR_INITRADIO):
                                RNS.log(str(self)+" hardware initialisation error (code "+RNS.hexrep(byte)+")")
                            elif (byte == KISS.ERROR_TXFAILED):
                                RNS.log(str(self)+" hardware TX error (code "+RNS.hexrep(byte)+")")
                            else:
                                RNS.log(str(self)+" hardware error (code "+RNS.hexrep(byte)+")")
                        elif (command == KISS.CMD_DETECT):
                            if byte == KISS.DETECT_RESP:
                                self.detected = True
                            else:
                                self.detected = False
                        
                else:
                    time_since_last = int(time.time()*1000) - last_read_ms
                    if len(data_buffer) > 0 and time_since_last > self.timeout:
                        RNS.log(str(self)+" serial read timeout")
                        data_buffer = b""
                        in_frame = False
                        command = KISS.CMD_UNKNOWN
                        escape = False
                    sleep(0.08)

        except Exception as e:
            raise e
            exit()

    def updateBitrate(self):
        try:
            self.bitrate = self.r_sf * ( (4.0/self.r_cr) / (math.pow(2,self.r_sf)/(self.r_bandwidth/1000)) ) * 1000
            self.bitrate_kbps = round(self.bitrate/1000.0, 2)
        except Exception as e:
            self.bitrate = 0

    def updateVersion(self):
        minstr = str(self.minor_version)
        if len(minstr) == 1:
            minstr = "0"+minstr
        self.version = str(self.major_version)+"."+minstr

    def detect(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_DETECT, KISS.DETECT_REQ, KISS.FEND, KISS.CMD_FW_VERSION, 0x00, KISS.FEND, KISS.CMD_PLATFORM, 0x00, KISS.FEND, KISS.CMD_MCU, 0x00, KISS.FEND, KISS.CMD_BOARD, 0x00, KISS.FEND, KISS.CMD_DEV_HASH, 0x01, KISS.FEND, KISS.CMD_HASHES, 0x02, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while detecting hardware for "+self(str))

    def leave(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_LEAVE, 0xFF, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending host left command to device")

    def enable_bluetooth(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x01, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending bluetooth enable command to device")

    def disable_bluetooth(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x00, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending bluetooth disable command to device")

    def bluetooth_pair(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x02, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending bluetooth pair command to device")

    def store_signature(self, signature_bytes):
        data = KISS.escape(signature_bytes)
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_DEV_SIG])+data+bytes([KISS.FEND])

        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending signature to device")

    def set_firmware_hash(self, hash_bytes):
        data = KISS.escape(hash_bytes)
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_FW_HASH])+data+bytes([KISS.FEND])

        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending firmware hash to device")

    def indicate_firmware_update(self):
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_FW_UPD])+bytes([0x01])+bytes([KISS.FEND])

        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending firmware update command to device")

    def initRadio(self):
        self.setFrequency()
        self.setBandwidth()
        self.setTXPower()
        self.setSpreadingFactor()
        self.setCodingRate()
        self.setRadioState(KISS.RADIO_STATE_ON)

    def setFrequency(self):
        c1 = self.frequency >> 24
        c2 = self.frequency >> 16 & 0xFF
        c3 = self.frequency >> 8 & 0xFF
        c4 = self.frequency & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_FREQUENCY])+data+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring frequency for "+self(str))

    def setBandwidth(self):
        c1 = self.bandwidth >> 24
        c2 = self.bandwidth >> 16 & 0xFF
        c3 = self.bandwidth >> 8 & 0xFF
        c4 = self.bandwidth & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_BANDWIDTH])+data+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring bandwidth for "+self(str))

    def setTXPower(self):
        txp = bytes([self.txpower])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_TXPOWER])+txp+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring TX power for "+self(str))

    def setSpreadingFactor(self):
        sf = bytes([self.sf])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_SF])+sf+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring spreading factor for "+self(str))

    def setCodingRate(self):
        cr = bytes([self.cr])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_CR])+cr+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring coding rate for "+self(str))

    def setRadioState(self, state):
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_RADIO_STATE])+bytes([state])+bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring radio state for "+self(str))

    def setNormalMode(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_CONF_DELETE, 0x00, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring device mode")

    def setTNCMode(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_CONF_SAVE, 0x00, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring device mode")

        if self.platform == ROM.PLATFORM_ESP32:
            self.hard_reset()

    def wipe_eeprom(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_ROM_WIPE, 0xf8, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while wiping EEPROM")
        sleep(13);

    def hard_reset(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_RESET, 0xf8, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while restarting device")
        sleep(2);

    def write_eeprom(self, addr, byte):
        write_payload = b"" + bytes([addr, byte])
        write_payload = KISS.escape(write_payload)
        kiss_command = bytes([KISS.FEND, KISS.CMD_ROM_WRITE]) + write_payload + bytes([KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while writing EEPROM")


    def download_eeprom(self):
        self.eeprom = None
        kiss_command = bytes([KISS.FEND, KISS.CMD_ROM_READ, 0x00, KISS.FEND])
        written = self.serial.write(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring radio state")

        sleep(0.6)
        if self.eeprom == None:
            RNS.log("Could not download EEPROM from device. Is a valid firmware installed?")
            exit()
        else:
            self.parse_eeprom()

    def parse_eeprom(self):
        global squashvw;
        try:
            if self.eeprom[ROM.ADDR_INFO_LOCK] == ROM.INFO_LOCK_BYTE:
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.backends import default_backend

                self.provisioned = True

                self.product = self.eeprom[ROM.ADDR_PRODUCT]
                self.model = self.eeprom[ROM.ADDR_MODEL]
                self.hw_rev = self.eeprom[ROM.ADDR_HW_REV]
                self.serialno = bytes([self.eeprom[ROM.ADDR_SERIAL], self.eeprom[ROM.ADDR_SERIAL+1], self.eeprom[ROM.ADDR_SERIAL+2], self.eeprom[ROM.ADDR_SERIAL+3]])
                self.made = bytes([self.eeprom[ROM.ADDR_MADE], self.eeprom[ROM.ADDR_MADE+1], self.eeprom[ROM.ADDR_MADE+2], self.eeprom[ROM.ADDR_MADE+3]])
                self.checksum = b""


                self.min_freq = models[self.model][0]
                self.max_freq = models[self.model][1]
                self.max_output = models[self.model][2]

                try:
                    self.min_freq = models[self.model][0]
                    self.max_freq = models[self.model][1]
                    self.max_output = models[self.model][2]
                except Exception as e:
                    RNS.log("Exception")
                    RNS.log(str(e))
                    self.min_freq = 0
                    self.max_freq = 0
                    self.max_output = 0

                for i in range(0,16):
                    self.checksum = self.checksum+bytes([self.eeprom[ROM.ADDR_CHKSUM+i]])

                self.signature = b""
                for i in range(0,128):
                    self.signature = self.signature+bytes([self.eeprom[ROM.ADDR_SIGNATURE+i]])

                checksummed_info = b"" + bytes([self.product]) + bytes([self.model]) + bytes([self.hw_rev]) + self.serialno + self.made
                digest = hashes.Hash(hashes.MD5(), backend=default_backend())
                digest.update(checksummed_info)
                checksum = digest.finalize()

                if self.checksum != checksum:
                    self.provisioned = False
                    RNS.log("EEPROM checksum mismatch")
                    exit()
                else:
                    RNS.log("EEPROM checksum correct")

                    from cryptography.hazmat.primitives import serialization
                    from cryptography.hazmat.primitives.serialization import load_der_public_key
                    from cryptography.hazmat.primitives.serialization import load_der_private_key
                    from cryptography.hazmat.primitives.asymmetric import padding

                    # Try loading local signing key for 
                    # validation of self-signed devices
                    if os.path.isdir(FWD_DIR) and os.path.isfile(FWD_DIR+"/signing.key"):
                        private_bytes = None
                        try:
                            file = open(FWD_DIR+"/signing.key", "rb")
                            private_bytes = file.read()
                            file.close()
                        except Exception as e:
                            RNS.log("Could not load local signing key")

                        try:
                            private_key = serialization.load_der_private_key(
                                private_bytes,
                                password=None,
                                backend=default_backend()
                            )
                            public_key = private_key.public_key()
                            public_bytes = public_key.public_bytes(
                                encoding=serialization.Encoding.DER,
                                format=serialization.PublicFormat.SubjectPublicKeyInfo
                            )
                            public_bytes_hex = RNS.hexrep(public_bytes, delimit=False)

                            vendor_keys = []
                            for known in known_keys:
                                vendor_keys.append(known[1])

                            if not public_bytes_hex in vendor_keys:
                                local_key_entry = ["LOCAL", public_bytes_hex]
                                known_keys.append(local_key_entry)

                        except Exception as e:
                            RNS.log("Could not deserialize local signing key")
                            RNS.log(str(e))

                    for known in known_keys:
                        vendor = known[0]
                        public_hexrep = known[1]
                        public_bytes = bytes.fromhex(public_hexrep)
                        public_key = load_der_public_key(public_bytes, backend=default_backend())
                        try:
                            public_key.verify(
                                self.signature,
                                self.checksum,
                                padding.PSS(
                                    mgf=padding.MGF1(hashes.SHA256()),
                                    salt_length=padding.PSS.MAX_LENGTH
                                ),
                                hashes.SHA256())
                            if vendor == "LOCAL":
                                self.locally_signed = True

                            self.signature_valid = True
                            self.vendor = vendor
                        except Exception as e:
                            pass

                    if self.signature_valid:
                        RNS.log("Device signature validated")
                    else:
                        RNS.log("Device signature validation failed")
                        if not squashvw:
                            print("     ")
                            print("     WARNING! This device is NOT verifiable and should NOT be trusted.")
                            print("     Someone could have added privacy-breaking or malicious code to it.")
                            print("     ")
                            print("     Proceed at your own risk and responsibility! If you created this")
                            print("     device yourself, please read the documentation on how to sign your")
                            print("     device to avoid this warning.")
                            print("     ")
                            print("     Always use a firmware downloaded as binaries or compiled from source")
                            print("     from one of the following locations:")
                            print("     ")
                            print("        https://unsigned.io/rnode")
                            print("        https://github.com/markqvist/rnode_firmware")
                            print("     ")
                            print("     You can reflash and bootstrap this device to a verifiable state")
                            print("     by using this utility. It is recommended to do so NOW!")
                            print("     ")
                            print("     To initialise this device to a verifiable state, please run:")
                            print("     ")
                            print("              rnodeconf "+str(self.serial.name)+" --autoinstall")
                            print("")



                if self.eeprom[ROM.ADDR_CONF_OK] == ROM.CONF_OK_BYTE:
                    self.configured = True
                    self.conf_sf = self.eeprom[ROM.ADDR_CONF_SF]
                    self.conf_cr = self.eeprom[ROM.ADDR_CONF_CR]
                    self.conf_txpower = self.eeprom[ROM.ADDR_CONF_TXP]
                    self.conf_frequency = self.eeprom[ROM.ADDR_CONF_FREQ] << 24 | self.eeprom[ROM.ADDR_CONF_FREQ+1] << 16 | self.eeprom[ROM.ADDR_CONF_FREQ+2] << 8 | self.eeprom[ROM.ADDR_CONF_FREQ+3]
                    self.conf_bandwidth = self.eeprom[ROM.ADDR_CONF_BW] << 24 | self.eeprom[ROM.ADDR_CONF_BW+1] << 16 | self.eeprom[ROM.ADDR_CONF_BW+2] << 8 | self.eeprom[ROM.ADDR_CONF_BW+3]
                else:
                    self.configured = False
            else:
                self.provisioned = False
        except Exception as e:
            self.provisioned = False
            RNS.log("Invalid EEPROM data, could not parse device EEPROM.")


    def device_probe(self):
        sleep(2.5)
        self.detect()
        sleep(0.75)
        if self.detected == True:
            RNS.log("Device connected")
            RNS.log("Current firmware version: "+self.version)
            return True
        else:
            raise IOError("Got invalid response while detecting device")

selected_version = None
selected_hash = None
firmware_version_url = "https://unsigned.io/firmware/latest/?v="+program_version+"&variant="
fallback_firmware_version_url = "https://github.com/markqvist/rnode_firmware/releases/latest/download/release.json"
def ensure_firmware_file(fw_filename):
    global selected_version, selected_hash, upd_nocheck
    if fw_filename == "extracted_rnode_firmware.zip":
        vfpath = EXT_DIR+"/extracted_rnode_firmware.version"
        if os.path.isfile(vfpath):
            required_files = [
                "extracted_console_image.bin",
                "extracted_rnode_firmware.bin",
                "extracted_rnode_firmware.boot_app0",
                "extracted_rnode_firmware.bootloader",
                "extracted_rnode_firmware.partitions",
            ]
            parts_missing = False
            for rf in required_files:
                if not os.path.isfile(EXT_DIR+"/"+rf):
                    parts_missing = True

            if parts_missing:
                RNS.log("One or more required firmware files are missing from the extracted RNode")
                RNS.log("Firmware archive. Installation cannot continue. Please try extracting the")
                RNS.log("firmware again with the --extract-firmware option.")
                exit(184)

            vf = open(vfpath, "rb")
            release_info = vf.read().decode("utf-8").strip()
            selected_version = release_info.split()[0]
            selected_hash = release_info.split()[1]
            RNS.log("Using existing firmware file: "+fw_filename+" for version "+selected_version)
        else:
            RNS.log("No extracted firmware is available, cannot continue.")
            RNS.log("Extract a firmware from an existing RNode first, using the --extract-firmware option.")
            exit(183)

    else:
        try:
            if selected_version == None:
                if not upd_nocheck:
                    try:
                        try:
                            urlretrieve(firmware_version_url+fw_filename, UPD_DIR+"/"+fw_filename+".version.latest")
                        except Exception as e:
                            RNS.log("")
                            RNS.log("WARNING!")
                            RNS.log("Failed to retrieve latest version information for your board from the default server")
                            RNS.log("Will retry using the following fallback URL: "+fallback_firmware_version_url)
                            RNS.log("")
                            RNS.log("Hit enter if you want to proceed")
                            input()
                            try:
                                urlretrieve(fallback_firmware_version_url, UPD_DIR+"/fallback_release_info.json")
                                import json
                                with open(UPD_DIR+"/fallback_release_info.json", "rb") as rif:
                                    rdat = json.loads(rif.read())
                                    variant = rdat[fw_filename]
                                    with open(UPD_DIR+"/"+fw_filename+".version.latest", "wb") as verf:
                                        inf_str = str(variant["version"])+" "+str(variant["hash"])
                                        verf.write(inf_str.encode("utf-8"))

                            except Exception as e:
                                RNS.log("Error while trying fallback URL: "+str(e))
                                raise e

                    except Exception as e:
                        RNS.log("Failed to retrive latest version information for your board.")
                        RNS.log("Check your internet connection and try again.")
                        RNS.log("If you don't have Internet access currently, use the --fw-version option to manually specify a version.")
                        exit()

                    import shutil
                    file = open(UPD_DIR+"/"+fw_filename+".version.latest", "rb")
                    release_info = file.read().decode("utf-8").strip()
                    selected_version = release_info.split()[0]
                    selected_hash = release_info.split()[1]
                    if not os.path.isdir(UPD_DIR+"/"+selected_version):
                        os.makedirs(UPD_DIR+"/"+selected_version)
                    shutil.copy(UPD_DIR+"/"+fw_filename+".version.latest", UPD_DIR+"/"+selected_version+"/"+fw_filename+".version")
                    RNS.log("The latest firmware for this board is version "+selected_version)

                else:
                    RNS.log("Online firmware version check was disabled, but no firmware version specified for install.")
                    RNS.log("use the --fw-version option to manually specify a version.")
                    exit(98)

            update_target_url = firmware_update_url+selected_version+"/"+fw_filename

            try:
                if not os.path.isdir(UPD_DIR+"/"+selected_version):
                    os.makedirs(UPD_DIR+"/"+selected_version)

                if not os.path.isfile(UPD_DIR+"/"+selected_version+"/"+fw_filename):
                    RNS.log("Downloading missing firmware file: "+fw_filename+" for version "+selected_version)
                    urlretrieve(update_target_url, UPD_DIR+"/"+selected_version+"/"+fw_filename)
                    RNS.log("Firmware file downloaded")
                else:
                    RNS.log("Using existing firmware file: "+fw_filename+" for version "+selected_version)

                try:
                    if selected_hash == None:
                        try:
                            file = open(UPD_DIR+"/"+selected_version+"/"+fw_filename+".version", "rb")
                            release_info = file.read().decode("utf-8").strip()
                            selected_hash = release_info.split()[1]
                        except Exception as e:
                            RNS.log("Could not read locally cached release information.")
                            RNS.log("You can clear the cache with the --clear-cache option and try again.")

                        if selected_hash == None:
                            RNS.log("No release hash found for "+fw_filename+". The firmware integrity could not be verified.")
                            exit(97)

                    RNS.log("Verifying firmware integrity...")
                    fw_file = open(UPD_DIR+"/"+selected_version+"/"+fw_filename, "rb")
                    expected_hash = bytes.fromhex(selected_hash)
                    file_hash = hashlib.sha256(fw_file.read()).hexdigest()
                    if file_hash == selected_hash:
                        pass
                    else:
                        RNS.log("")
                        RNS.log("Firmware corrupt. Try clearing the local firmware cache with: rnodeconf --clear-cache")
                        exit(96)

                except Exception as e:
                    RNS.log("An error occurred while checking firmware file integrity. The contained exception was:")
                    RNS.log(str(e))
                    exit(95)

            except Exception as e:
                RNS.log("Could not download required firmware file: ")
                RNS.log(str(update_target_url))
                RNS.log("The contained exception was:")
                RNS.log(str(e))
                exit()

        except Exception as e:
            RNS.log("An error occurred while reading version information for "+str(fw_filename)+". The contained exception was:")
            RNS.log(str(e))
            exit()

def rnode_open_serial(port):
    import serial
    return serial.Serial(
        port = port,
        baudrate = rnode_baudrate,
        bytesize = 8,
        parity = serial.PARITY_NONE,
        stopbits = 1,
        xonxoff = False,
        rtscts = False,
        timeout = 0,
        inter_byte_timeout = None,
        write_timeout = None,
        dsrdtr = False
    )

device_signer = None
force_update = False
upd_nocheck = False
def main():
    global mapped_product, mapped_model, fw_filename, selected_version, force_update, upd_nocheck, device_signer

    try:
        if not util.find_spec("serial"):
            raise ImportError("Serial module could not be found")
    except ImportError:
        print("")
        print("RNode Config Utility needs pyserial to work.")
        print("You can install it with: pip3 install pyserial")
        print("")
        exit()

    try:
        if not util.find_spec("cryptography"):
            raise ImportError("Cryptography module could not be found")
    except ImportError:
        print("")
        print("RNode Config Utility needs the cryptography module to work.")
        print("You can install it with: pip3 install cryptography")
        print("")
        exit()

    import serial
    from serial.tools import list_ports

    try:
        parser = argparse.ArgumentParser(description="RNode Configuration and firmware utility. This program allows you to change various settings and startup modes of RNode. It can also install, flash and update the firmware on supported devices.")
        parser.add_argument("-i", "--info", action="store_true", help="Show device info")
        parser.add_argument("-a", "--autoinstall", action="store_true", help="Automatic installation on various supported devices")
        parser.add_argument("-u", "--update", action="store_true", help="Update firmware to the latest version")
        parser.add_argument("-U", "--force-update", action="store_true", help="Update to specified firmware even if version matches or is older than installed version")
        parser.add_argument("--fw-version", action="store", metavar="version", default=None, help="Use a specific firmware version for update or autoinstall")
        parser.add_argument("--nocheck", action="store_true", help="Don't check for firmware updates online")
        parser.add_argument("-e", "--extract", action="store_true", help="Extract firmware from connected RNode for later use")
        parser.add_argument("-E", "--use-extracted", action="store_true", help="Use the extracted firmware for autoinstallation or update")
        parser.add_argument("-C", "--clear-cache", action="store_true", help="Clear locally cached firmware files")
        
        parser.add_argument("-N", "--normal", action="store_true", help="Switch device to normal mode")
        parser.add_argument("-T", "--tnc", action="store_true", help="Switch device to TNC mode")

        parser.add_argument("-b", "--bluetooth-on", action="store_true", help="Turn device bluetooth on")
        parser.add_argument("-B", "--bluetooth-off", action="store_true", help="Turn device bluetooth off")
        parser.add_argument("-p", "--bluetooth-pair", action="store_true", help="Put device into bluetooth pairing mode")

        parser.add_argument("--freq", action="store", metavar="Hz", type=int, default=None, help="Frequency in Hz for TNC mode")
        parser.add_argument("--bw", action="store", metavar="Hz", type=int, default=None, help="Bandwidth in Hz for TNC mode")
        parser.add_argument("--txp", action="store", metavar="dBm", type=int, default=None, help="TX power in dBm for TNC mode")
        parser.add_argument("--sf", action="store", metavar="factor", type=int, default=None, help="Spreading factor for TNC mode (7 - 12)")
        parser.add_argument("--cr", action="store", metavar="rate", type=int, default=None, help="Coding rate for TNC mode (5 - 8)")

        parser.add_argument("--eeprom-backup", action="store_true", help="Backup EEPROM to file")
        parser.add_argument("--eeprom-dump", action="store_true", help="Dump EEPROM to console")
        parser.add_argument("--eeprom-wipe", action="store_true", help="Unlock and wipe EEPROM")

        parser.add_argument("--version", action="store_true", help="Print program version and exit")

        parser.add_argument("-f", "--flash", action="store_true", help=argparse.SUPPRESS) # Flash firmware and bootstrap EEPROM
        parser.add_argument("-r", "--rom", action="store_true", help=argparse.SUPPRESS) # Bootstrap EEPROM without flashing firmware
        parser.add_argument("-k", "--key", action="store_true", help=argparse.SUPPRESS) # Generate a new signing key and exit
        parser.add_argument("-P", "--public", action="store_true", help=argparse.SUPPRESS) # Display public part of signing key
        parser.add_argument("-S", "--sign", action="store_true", help=argparse.SUPPRESS) # Display public part of signing key
        parser.add_argument("-H", "--firmware-hash", action="store", help=argparse.SUPPRESS) # Display public part of signing key
        parser.add_argument("--platform", action="store", metavar="platform", type=str, default=None, help=argparse.SUPPRESS) # Platform specification for device bootstrap
        parser.add_argument("--product", action="store", metavar="product", type=str, default=None, help=argparse.SUPPRESS) # Product specification for device bootstrap
        parser.add_argument("--model", action="store", metavar="model", type=str, default=None, help=argparse.SUPPRESS) # Model code for device bootstrap
        parser.add_argument("--hwrev", action="store", metavar="revision", type=int, default=None, help=argparse.SUPPRESS) # Hardware revision for device bootstrap

        parser.add_argument("port", nargs="?", default=None, help="serial port where RNode is attached", type=str)
        args = parser.parse_args()

        def print_donation_block():
            print("  Ethereum : "+eth_addr)
            print("  Bitcoin  : "+btc_addr)
            print("  Monero   : "+xmr_addr)
            print("  Ko-Fi    : https://ko-fi.com/markqvist")
            print("")
            print("  Info     : https://unsigned.io/")
            print("  Code     : https://github.com/markqvist")

        if args.version:
            print("rnodeconf "+program_version)
            exit(0)

        if args.clear_cache:
            RNS.log("Clearing local firmware cache...")
            import shutil
            shutil.rmtree(UPD_DIR)
            RNS.log("Done")
            exit(0)

        if args.fw_version != None:
            selected_version = args.fw_version

        if args.force_update:
            force_update = True

        if args.nocheck:
            upd_nocheck = True
            
        if args.public or args.key or args.flash or args.rom or args.autoinstall:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            from cryptography.hazmat.primitives.serialization import load_der_private_key
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives.asymmetric import padding

        clear = lambda: os.system('clear')

        if args.use_extracted and ((args.update and args.port != None) or args.autoinstall):
            print("")
            print("You have specified that rnodeconf should use a firmware extracted")
            print("from another device. Please note that this *only* works if you are")
            print("targeting a device of the same type that the firmware came from!")
            print("")
            print("Flashing this firmware to a device it was not created for will most")
            print("likely result in it being inoperable until it is updated with the")
            print("correct firmware. Hit enter to continue.")
            input()

        if args.extract:
            # clear()
            print("")
            print("RNode Firmware Extraction")
            print("")
            if not args.port:
                ports = list_ports.comports()
                portlist = []
                for port in ports:
                    portlist.insert(0, port) 
                
                pi = 1
                print("Detected serial ports:")
                for port in portlist:
                    print("  ["+str(pi)+"] "+str(port.device)+" ("+str(port.product)+", "+str(port.serial_number)+")")
                    pi += 1

                print("\nEnter the number of the serial port your device is connected to:\n? ", end="")
                try:
                    c_port = int(input())
                    if c_port < 1 or c_port > len(ports):
                        raise ValueError()

                    selected_port = portlist[c_port-1]
                except Exception as e:
                    print("That port does not exist, exiting now.")
                    exit()

                if selected_port == None:
                    print("Could not select port, exiting now.")
                    exit()

                port_path = selected_port.device
                port_product = selected_port.product
                port_serialno = selected_port.serial_number

                print("\nOk, using device on "+str(port_path)+" ("+str(port_product)+", "+str(port_serialno)+")")

            else:
                ports = list_ports.comports()

                for port in ports:
                    if port.device == args.port:
                        selected_port = port

                if selected_port == None:
                    print("Could not find specified port "+str(args.port)+", exiting now")
                    exit()

                port_path = selected_port.device
                port_product = selected_port.product
                port_serialno = selected_port.serial_number

                print("\nUsing device on "+str(port_path))

            print("\nProbing device...")

            try:
                rnode_serial = rnode_open_serial(port_path)
            except Exception as e:
                RNS.log("Could not open the specified serial port. The contained exception was:")
                RNS.log(str(e))
                exit()

            rnode = RNode(rnode_serial)
            thread = threading.Thread(target=rnode.readLoop, daemon=True).start()
            try:
                rnode.device_probe()
            except Exception as e:
                RNS.log("No answer from device")

            if rnode.detected:
                RNS.log("Trying to read EEPROM...")
                rnode.download_eeprom()
            else:
                RNS.log("Could not detect a connected RNode")

            if rnode.provisioned and rnode.signature_valid:
                if rnode.firmware_hash != None:
                    extracted_hash = rnode.firmware_hash
                    extracted_version = rnode.version
                    rnode.disconnect()
                    v_str = str(extracted_version)+" "+RNS.hexrep(extracted_hash, delimit=False)
                    print("\nFound RNode Firmvare v"+v_str)

                    print("\nReady to extract firmware images from the RNode")
                    print("Press enter to start the extraction process")
                    input()
                    extract_recovery_esptool()

                    hash_f = open(EXT_DIR+"/extracted_rnode_firmware.version", "wb")
                    hash_f.write(v_str.encode("utf-8"))
                    hash_f.close()

                    extraction_parts = [
                        ("bootloader", "python \""+CNF_DIR+"/recovery_esptool.py\" --chip esp32 --port /dev/ttyACM1 --baud 921600 --before default_reset --after hard_reset read_flash 0x1000 0x4650 \""+EXT_DIR+"/extracted_rnode_firmware.bootloader\""),
                        ("partition table", "python \""+CNF_DIR+"/recovery_esptool.py\" --chip esp32 --port /dev/ttyACM1 --baud 921600 --before default_reset --after hard_reset read_flash 0x8000 0xC00 \""+EXT_DIR+"/extracted_rnode_firmware.partitions\""),
                        ("app boot", "python \""+CNF_DIR+"/recovery_esptool.py\" --chip esp32 --port /dev/ttyACM1 --baud 921600 --before default_reset --after hard_reset read_flash 0xe000 0x2000 \""+EXT_DIR+"/extracted_rnode_firmware.boot_app0\""),
                        ("application image", "python \""+CNF_DIR+"/recovery_esptool.py\" --chip esp32 --port /dev/ttyACM1 --baud 921600 --before default_reset --after hard_reset read_flash 0x10000 0x200000 \""+EXT_DIR+"/extracted_rnode_firmware.bin\""),
                        ("console image", "python \""+CNF_DIR+"/recovery_esptool.py\" --chip esp32 --port /dev/ttyACM1 --baud 921600 --before default_reset --after hard_reset read_flash 0x210000 0x1F0000 \""+EXT_DIR+"/extracted_console_image.bin\""),
                    ]
                    import subprocess, shlex
                    for part, command in extraction_parts:
                        print("Extracting "+part+"...")
                        if subprocess.call(shlex.split(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                            print("The extraction failed, the following command did not complete successfully:\n"+command)
                            exit(182)

                    print("\nFirmware successfully extracted!")
                    print("\nYou can now use this firmware to update or autoinstall other RNodes")
                    exit()
                else:
                    print("Could not read firmware information from device")

            print("\nRNode firmware extraction failed")
            exit(180)

        if args.autoinstall:
            clear()
            if not args.port:
                print("\nHello!\n\nThis guide will help you install the RNode firmware on supported")
                print("and homebrew devices. Please connect the device you wish to set\nup now. Hit enter when it is connected.")
                input()

            global squashvw
            squashvw = True

            selected_port = None
            if not args.port:
                ports = list_ports.comports()
                portlist = []
                for port in ports:
                    portlist.insert(0, port) 
                
                pi = 1
                print("Detected serial ports:")
                for port in portlist:
                    print("  ["+str(pi)+"] "+str(port.device)+" ("+str(port.product)+", "+str(port.serial_number)+")")
                    pi += 1

                print("\nEnter the number of the serial port your device is connected to:\n? ", end="")
                try:
                    c_port = int(input())
                    if c_port < 1 or c_port > len(ports):
                        raise ValueError()

                    selected_port = portlist[c_port-1]
                except Exception as e:
                    print("That port does not exist, exiting now.")
                    exit()

                if selected_port == None:
                    print("Could not select port, exiting now.")
                    exit()

                port_path = selected_port.device
                port_product = selected_port.product
                port_serialno = selected_port.serial_number

                clear()
                print("\nOk, using device on "+str(port_path)+" ("+str(port_product)+", "+str(port_serialno)+")")

            else:
                ports = list_ports.comports()

                for port in ports:
                    if port.device == args.port:
                        selected_port = port

                if selected_port == None:
                    print("Could not find specified port "+str(args.port)+", exiting now")
                    exit()

                port_path = selected_port.device
                port_product = selected_port.product
                port_serialno = selected_port.serial_number

                print("\nUsing device on "+str(port_path))

            print("\nProbing device...")

            try:
                rnode_serial = rnode_open_serial(port_path)
            except Exception as e:
                RNS.log("Could not open the specified serial port. The contained exception was:")
                RNS.log(str(e))
                exit()

            rnode = RNode(rnode_serial)
            thread = threading.Thread(target=rnode.readLoop, daemon=True).start()
            try:
                rnode.device_probe()
            except Exception as e:
                RNS.log("No answer from device")

            if rnode.detected:
                RNS.log("Trying to read EEPROM...")
                rnode.download_eeprom()

            if rnode.provisioned and rnode.signature_valid:
                print("\nThis device is already installed and provisioned. No further action will")
                print("be taken. If you wish to completely reinstall this device, you must first")
                print("wipe the current EEPROM. See the help for more info.\n\nExiting now.")
                exit()

            print("\n---------------------------------------------------------------------------")
            print("                               Device Selection")
            if rnode.detected:
                print("\nThe device seems to have an RNode firmware installed, but it was not")
                print("provisioned correctly, or it is corrupt. We are going to reinstall the")
                print("correct firmware and provision it.")
            else:
                print("\nIt looks like this is a fresh device with no RNode firmware.")
                
            print("")
            print("What kind of device is this?\n")
            print("[1] A specific kind of RNode")
            print("       .")
            print("      / \\   Select this option if you have an RNode of a specific")
            print("       |    type, built from a recipe or bought from a vendor.")
            print("")
            print("[2] Homebrew RNode")
            print("       .")
            print("      / \\   Select this option if you have put toghether an RNode")
            print("       |    of your own design, or if you are prototyping one.")
            print("")
            print("[3] LilyGO LoRa32 v2.1 (aka T3 v1.6 / T3 v1.6.1)")
            print("[4] LilyGO LoRa32 v2.0")
            print("[5] LilyGO T-Beam")
            print("[6] Heltec LoRa32 v2")
            print("       .")
            print("      / \\   Select one of these options if you want to easily turn")
            print("       |    a supported development board into an RNode.")
            print("")
            print("---------------------------------------------------------------------------")
            print("\nEnter the number that matches your device type:\n? ", end="")

            selected_product = None
            try:
                c_dev = int(input())
                if c_dev < 1 or c_dev > 6:
                    raise ValueError()
                elif c_dev == 1:
                    selected_product = ROM.PRODUCT_RNODE
                elif c_dev == 2:
                    selected_product = ROM.PRODUCT_HMBRW
                    clear()
                    print("")
                    print("---------------------------------------------------------------------------")
                    print("                        Homebrew RNode Installer")
                    print("")
                    print("This option allows you to install and provision the RNode firmware on a")
                    print("custom board design, or a custom device created by coupling a generic")
                    print("development board with a supported transceiver module.")
                    print("")
                    print("Important! Using RNode firmware on homebrew devices should currently be")
                    print("considered experimental. It is not intended for production or critical use.")
                    print("The currently supplied firmware is provided AS-IS as a courtesey to those")
                    print("who would like to experiment with it. Hit enter to continue.")
                    print("---------------------------------------------------------------------------")
                    input()
                elif c_dev == 5:
                    selected_product = ROM.PRODUCT_TBEAM
                    clear()
                    print("")
                    print("---------------------------------------------------------------------------")
                    print("                          T-Beam RNode Installer")
                    print("")
                    print("The RNode firmware can currently be installed on T-Beam devices using the")
                    print("SX1276 and SX1278 transceiver chips. Support for devices with the newer")
                    print("SX1262 and SX1268 chips is in development.")
                    print("")
                    print("Important! Using RNode firmware on T-Beam devices should currently be")
                    print("considered experimental. It is not intended for production or critical use.")
                    print("The currently supplied firmware is provided AS-IS as a courtesey to those")
                    print("who would like to experiment with it. Hit enter to continue.")
                    print("---------------------------------------------------------------------------")
                    input()
                elif c_dev == 4:
                    selected_product = ROM.PRODUCT_T32_20
                    clear()
                    print("")
                    print("---------------------------------------------------------------------------")
                    print("                     LilyGO LoRa32 v2.0 RNode Installer")
                    print("")
                    print("Important! Using RNode firmware on LoRa32 devices should currently be")
                    print("considered experimental. It is not intended for production or critical use.")
                    print("The currently supplied firmware is provided AS-IS as a courtesey to those")
                    print("who would like to experiment with it. Hit enter to continue.")
                    print("---------------------------------------------------------------------------")
                    input()
                elif c_dev == 3:
                    selected_product = ROM.PRODUCT_T32_21
                    clear()
                    print("")
                    print("---------------------------------------------------------------------------")
                    print("                     LilyGO LoRa32 v2.1 RNode Installer")
                    print("")
                    print("Important! Using RNode firmware on LoRa32 devices should currently be")
                    print("considered experimental. It is not intended for production or critical use.")
                    print("The currently supplied firmware is provided AS-IS as a courtesey to those")
                    print("who would like to experiment with it. Hit enter to continue.")
                    print("---------------------------------------------------------------------------")
                    input()
                elif c_dev == 6:
                    selected_product = ROM.PRODUCT_H32_V2
                    clear()
                    print("")
                    print("---------------------------------------------------------------------------")
                    print("                     Heltec LoRa32 v2.0 RNode Installer")
                    print("")
                    print("Important! Using RNode firmware on Heltec devices should currently be")
                    print("considered experimental. It is not intended for production or critical use.")
                    print("")
                    print("Please also note that a number of users have reported issues with the serial")
                    print("to USB chips on Heltec LoRa V2 boards, resulting in intermittent USB comms")
                    print("and problems flashing and updating devices.")
                    print("")
                    print("The currently supplied firmware is provided AS-IS as a courtesey to those")
                    print("who would like to experiment with it. Hit enter to continue.")
                    print("---------------------------------------------------------------------------")
                    input()
            except Exception as e:
                print("That device type does not exist, exiting now.")
                exit()

            selected_platform = None
            selected_model = None
            selected_mcu = None

            if selected_product == ROM.PRODUCT_HMBRW:
                print("\nWhat kind of microcontroller is your board based on?\n")
                print("[1] AVR ATmega1284P")
                print("[2] AVR ATmega2560")
                print("[3] Espressif Systems ESP32")
                print("\n? ", end="")
                try:
                    c_mcu = int(input())
                    if c_mcu < 1 or c_mcu > 3:
                        raise ValueError()
                    elif c_mcu == 1:
                        selected_mcu = ROM.MCU_1284P
                        selected_platform = ROM.PLATFORM_AVR
                    elif c_mcu == 2:
                        selected_mcu = ROM.MCU_2560
                        selected_platform = ROM.PLATFORM_AVR
                    elif c_mcu == 3:
                        selected_mcu = ROM.MCU_ESP32
                        selected_platform = ROM.PLATFORM_ESP32
                    selected_model = ROM.MODEL_FF

                except Exception as e:
                    print("That MCU type does not exist, exiting now.")
                    exit()

                print("\nWhat transceiver module does your board use?\n")
                print("[1] SX1276/SX1278 with antenna port on PA_BOOST pin")
                print("[2] SX1276/SX1278 with antenna port on RFO pin")
                print("\n? ", end="")
                try:
                    c_trxm = int(input())
                    if c_trxm < 1 or c_trxm > 3:
                        raise ValueError()
                    elif c_trxm == 1:
                        selected_model = ROM.MODEL_FE
                    elif c_trxm == 2:
                        selected_model = ROM.MODEL_FF

                except Exception as e:
                    print("That transceiver type does not exist, exiting now.")
                    exit()


            elif selected_product == ROM.PRODUCT_RNODE:
                selected_mcu = ROM.MCU_1284P
                print("\nWhat model is this RNode?\n")
                print("[1] Handheld v2.x RNode, 410 - 525 MHz")
                print("[2] Handheld v2.x RNode, 820 - 1020 MHz")
                print("")
                print("[3] Original v1.x RNode, 410 - 525 MHz")
                print("[4] Original v1.x RNode, 820 - 1020 MHz")
                # print("[5] Prototype v2 RNode, 410 - 525 MHz")
                # print("[6] Prototype v2 RNode, 820 - 1020 MHz")
                print("\n? ", end="")
                try:
                    c_model = int(input())
                    if c_model < 1 or c_model > 6:
                        raise ValueError()
                    elif c_model == 3:
                        selected_model = ROM.MODEL_A4
                        selected_platform = ROM.PLATFORM_AVR
                    elif c_model == 4:
                        selected_model = ROM.MODEL_A9
                        selected_platform = ROM.PLATFORM_AVR
                    elif c_model == 1:
                        selected_model = ROM.MODEL_A2
                        selected_mcu = ROM.MCU_ESP32
                        selected_platform = ROM.PLATFORM_ESP32
                    elif c_model == 2:
                        selected_model = ROM.MODEL_A7
                        selected_mcu = ROM.MCU_ESP32
                        selected_platform = ROM.PLATFORM_ESP32
                    # elif c_model == 5:
                    #     selected_model = ROM.MODEL_A3
                    #     selected_mcu = ROM.MCU_ESP32
                    #     selected_platform = ROM.PLATFORM_ESP32
                    # elif c_model == 6:
                    #     selected_model = ROM.MODEL_A8
                    #     selected_mcu = ROM.MCU_ESP32
                    #     selected_platform = ROM.PLATFORM_ESP32
                except Exception as e:
                    print("That model does not exist, exiting now.")
                    exit()

            elif selected_product == ROM.PRODUCT_TBEAM:
                selected_mcu = ROM.MCU_ESP32
                print("\nWhat band is this T-Beam for?\n")
                print("[1] 433 MHz")
                print("[2] 868 MHz")
                print("[3] 915 MHz")
                print("[4] 923 MHz")
                print("\n? ", end="")
                try:
                    c_model = int(input())
                    if c_model < 1 or c_model > 4:
                        raise ValueError()
                    elif c_model == 1:
                        selected_model = ROM.MODEL_E4
                        selected_platform = ROM.PLATFORM_ESP32
                    elif c_model > 1:
                        selected_model = ROM.MODEL_E9
                        selected_platform = ROM.PLATFORM_ESP32
                except Exception as e:
                    print("That band does not exist, exiting now.")
                    exit()

            elif selected_product == ROM.PRODUCT_T32_20:
                selected_mcu = ROM.MCU_ESP32
                print("\nWhat band is this LoRa32 for?\n")
                print("[1] 433 MHz")
                print("[2] 868 MHz")
                print("[3] 915 MHz")
                print("[4] 923 MHz")
                print("\n? ", end="")
                try:
                    c_model = int(input())
                    if c_model < 1 or c_model > 4:
                        raise ValueError()
                    elif c_model == 1:
                        selected_model = ROM.MODEL_B3
                        selected_platform = ROM.PLATFORM_ESP32
                    elif c_model > 1:
                        selected_model = ROM.MODEL_B8
                        selected_platform = ROM.PLATFORM_ESP32
                except Exception as e:
                    print("That band does not exist, exiting now.")
                    exit()

            elif selected_product == ROM.PRODUCT_T32_21:
                selected_mcu = ROM.MCU_ESP32
                print("\nWhat band is this LoRa32 for?\n")
                print("[1] 433 MHz")
                print("[2] 868 MHz")
                print("[3] 915 MHz")
                print("[4] 923 MHz")
                print("\n? ", end="")
                try:
                    c_model = int(input())
                    if c_model < 1 or c_model > 4:
                        raise ValueError()
                    elif c_model == 1:
                        selected_model = ROM.MODEL_B4
                        selected_platform = ROM.PLATFORM_ESP32
                    elif c_model > 1:
                        selected_model = ROM.MODEL_B9
                        selected_platform = ROM.PLATFORM_ESP32
                except Exception as e:
                    print("That band does not exist, exiting now.")
                    exit()

            elif selected_product == ROM.PRODUCT_H32_V2:
                selected_mcu = ROM.MCU_ESP32
                print("\nWhat band is this Heltec LoRa32 for?\n")
                print("[1] 433 MHz")
                print("[2] 868 MHz")
                print("[3] 915 MHz")
                print("[4] 923 MHz")
                print("\n? ", end="")
                try:
                    c_model = int(input())
                    if c_model < 1 or c_model > 4:
                        raise ValueError()
                    elif c_model == 1:
                        selected_model = ROM.MODEL_C4
                        selected_platform = ROM.PLATFORM_ESP32
                    elif c_model > 1:
                        selected_model = ROM.MODEL_C9
                        selected_platform = ROM.PLATFORM_ESP32
                except Exception as e:
                    print("That band does not exist, exiting now.")
                    exit()

            if selected_model != ROM.MODEL_FF and selected_model != ROM.MODEL_FE:
                fw_filename = models[selected_model][4]

            else:
                if selected_platform == ROM.PLATFORM_AVR:
                    if selected_mcu == ROM.MCU_1284P:
                        fw_filename = "rnode_firmware.hex"
                    elif selected_mcu == ROM.MCU_2560:
                        fw_filename = "rnode_firmware_m2560.hex"
                
                elif selected_platform == ROM.PLATFORM_ESP32:
                    fw_filename = None
                    print("\nWhat kind of ESP32 board is this?\n")
                    print("[1] Adafruit Feather ESP32 (HUZZAH32)")
                    print("[2] Generic ESP32 board")
                    print("\n? ", end="")
                    try:
                        c_eboard = int(input())
                        if c_eboard < 1 or c_eboard > 2:
                            raise ValueError()
                        elif c_eboard == 1:
                            fw_filename = "rnode_firmware_featheresp32.zip"
                        elif c_eboard == 2:
                            fw_filename = "rnode_firmware_esp32_generic.zip"
                    except Exception as e:
                        print("That ESP32 board does not exist, exiting now.")
                        exit()
            
            if fw_filename == None:
                print("")
                print("Sorry, no firmware for your board currently exists.")
                print("Help making it a reality by contributing code or by")
                print("donating to the project.")
                print("")
                print_donation_block()
                print("")
                exit()

            if args.use_extracted:
                fw_filename = "extracted_rnode_firmware.zip"

            clear()
            print("")
            print("------------------------------------------------------------------------------")
            print("                               Installer Ready")
            print("")
            print("Ok, that should be all the information we need. Please confirm the following")
            print("summary before proceeding. In the next step, the device will be flashed and")
            print("provisioned, so make sure that you are satisfied with your choices.\n")

            print("Serial port     : "+str(selected_port.device))
            print("Device type     : "+str(products[selected_product])+" "+str(models[selected_model][3]))
            print("Platform        : "+str(platforms[selected_platform]))
            print("Device MCU      : "+str(mcus[selected_mcu]))
            print("Firmware file   : "+str(fw_filename))

            print("")
            print("------------------------------------------------------------------------------")

            print("\nIs the above correct? [y/N] ", end="")
            try:
                c_ok = input().lower()
                if c_ok != "y":
                    raise ValueError()
            except Exception as e:
                print("OK, aborting now.")
                exit()

            args.key = True
            args.port = selected_port.device
            args.platform = selected_platform
            args.hwrev = 1
            mapped_model = selected_model
            mapped_product = selected_product
            args.update = False
            args.flash = True

            try:
                RNS.log("Checking firmware file availability...")
                ensure_firmware_file(fw_filename)
            except Exception as e:
                RNS.log("Could not obain firmware package for your board")
                RNS.log("The contained exception was: "+str(e))
                exit()

            rnode.disconnect()

        if args.public:
            private_bytes = None
            try:
                file = open(FWD_DIR+"/signing.key", "rb")
                private_bytes = file.read()
                file.close()
            except Exception as e:
                RNS.log("Could not load EEPROM signing key")

            try:
                private_key = serialization.load_der_private_key(
                    private_bytes,
                    password=None,
                    backend=default_backend()
                )
                public_key = private_key.public_key()
                public_bytes = public_key.public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                RNS.log("EEPROM Signing Public key:")
                RNS.log(RNS.hexrep(public_bytes, delimit=False))

            except Exception as e:
                RNS.log("Could not deserialize signing key")
                RNS.log(str(e))

            try:
                device_signer = RNS.Identity.from_file(FWD_DIR+"/device.key")
                RNS.log("")
                RNS.log("Device Signing Public key:")
                RNS.log(RNS.hexrep(device_signer.get_public_key()[32:], delimit=True))

            except Exception as e:
                RNS.log("Could not load device signing key")
                

            exit()

        if args.key:
            if not os.path.isfile(FWD_DIR+"/device.key"):
                try:
                    RNS.log("Generating a new device signing key...")
                    device_signer = RNS.Identity()
                    device_signer.to_file(FWD_DIR+"/device.key")
                    RNS.log("Device signing key written to "+str(FWD_DIR+"/device.key"))
                except Exception as e:
                    RNS.log("Could not create new device signing key at "+str(FWD_DIR+"/device.key")+". The contained exception was:")
                    RNS.log(str(e))
                    RNS.log("Please ensure filesystem access and try again.")
                    exit(81)
            else:
                try:
                    device_signer = RNS.Identity.from_file(FWD_DIR+"/device.key")
                except Exception as e:
                    RNS.log("Could not load device signing key from "+str(FWD_DIR+"/device.key")+". The contained exception was:")
                    RNS.log(str(e))
                    RNS.log("Please restore or clear the key and try again.")
                    exit(82)

            if not os.path.isfile(FWD_DIR+"/signing.key"):
                RNS.log("Generating a new EEPROM signing key...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=1024,
                backend=default_backend()
            )
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key = private_key.public_key()
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            os.makedirs(FWD_DIR, exist_ok=True)
            if os.path.isdir(FWD_DIR):
                if os.path.isfile(FWD_DIR+"/signing.key"):
                    if not args.autoinstall:
                        RNS.log("EEPROM Signing key already exists, not overwriting!")
                        RNS.log("Manually delete this key to create a new one.")
                else:
                    file = open(FWD_DIR+"/signing.key", "wb")
                    file.write(private_bytes)
                    file.close()

                    if not squashvw:
                        RNS.log("Wrote signing key")
                        RNS.log("Public key:")
                        RNS.log(RNS.hexrep(public_bytes, delimit=False))
            else:
                RNS.log("The firmware directory does not exist, can't write key!")

            if not args.autoinstall:
                exit()

        def get_partition_hash(partition_file):
            try:
                firmware_data = open(partition_file, "rb").read()
                calc_hash = hashlib.sha256(firmware_data[0:-32]).digest()
                part_hash = firmware_data[-32:]

                if calc_hash == part_hash:
                    return part_hash
                else:
                    return None
            except Exception as e:
                RNS.log("Could not calculate firmware partition hash. The contained exception was:")
                RNS.log(str(e))

        def get_flasher_call(platform, fw_filename):
            global selected_version
            from shutil import which
            if platform == "unzip":
                flasher = "unzip"
                if which(flasher) is not None:
                    return [flasher, "-o", UPD_DIR+"/"+selected_version+"/"+fw_filename, "-d", UPD_DIR+"/"+selected_version]
                else:
                    RNS.log("")
                    RNS.log("You do not currently have the \""+flasher+"\" program installed on your system.")
                    RNS.log("Unfortunately, that means we can't proceed, since it is needed to flash your")
                    RNS.log("board. You can install it via your package manager, for example:")
                    RNS.log("")
                    RNS.log("  sudo apt install "+flasher)
                    RNS.log("")
                    RNS.log("Please install \""+flasher+"\" and try again.")
                    exit()
            elif platform == ROM.PLATFORM_AVR:
                flasher = "avrdude"
                if which(flasher) is not None:
                    # avrdude -C/home/markqvist/.arduino15/packages/arduino/tools/avrdude/6.3.0-arduino17/etc/avrdude.conf -q -q -V -patmega2560 -cwiring -P/dev/ttyACM0 -b115200 -D -Uflash:w:/tmp/arduino-sketch-0E260F46C421A84A7CBAD48E859C8E64/RNode_Firmware.ino.hex:i
                    # avrdude -q -q -V -patmega2560 -cwiring -P/dev/ttyACM0 -b115200 -D -Uflash:w:/tmp/arduino-sketch-0E260F46C421A84A7CBAD48E859C8E64/RNode_Firmware.ino.hex:i
                    if fw_filename == "rnode_firmware.hex":
                        return [flasher, "-P", args.port, "-p", "m1284p", "-c", "arduino", "-b", "115200", "-U", "flash:w:"+UPD_DIR+"/"+selected_version+"/"+fw_filename+":i"]
                    elif fw_filename == "rnode_firmware_m2560.hex":
                        return [flasher, "-P", args.port, "-p", "atmega2560", "-c", "wiring", "-D", "-b", "115200", "-U", "flash:w:"+UPD_DIR+"/"+selected_version+"/"+fw_filename]
                else:
                    RNS.log("")
                    RNS.log("You do not currently have the \""+flasher+"\" program installed on your system.")
                    RNS.log("Unfortunately, that means we can't proceed, since it is needed to flash your")
                    RNS.log("board. You can install it via your package manager, for example:")
                    RNS.log("")
                    RNS.log("  sudo apt install avrdude")
                    RNS.log("")
                    RNS.log("Please install \""+flasher+"\" and try again.")
                    exit()
            elif platform == ROM.PLATFORM_ESP32:
                numeric_version = float(selected_version)
                flasher_dir = UPD_DIR+"/"+selected_version
                flasher = flasher_dir+"/esptool.py"
                if not os.path.isfile(flasher):
                    if os.path.isfile(CNF_DIR+"/recovery_esptool.py"):
                        import shutil
                        if not os.path.isdir(flasher_dir):
                            os.makedirs(flasher_dir)
                        shutil.copy(CNF_DIR+"/recovery_esptool.py", flasher)
                        RNS.log("No flasher present, using recovery flasher to write firmware to device")

                if os.path.isfile(flasher):
                    import stat
                    os.chmod(flasher, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

                if which(flasher) is not None:
                    if fw_filename == "rnode_firmware_tbeam.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_tbeam.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_lora32v20.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v20.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_lora32v21.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_lora32v21.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_heltec32v2.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "8MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "8MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_heltec32v2.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_featheresp32.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_featheresp32.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_esp32_generic.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_esp32_generic.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_ng20.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng20.partitions",
                            ]
                    elif fw_filename == "rnode_firmware_ng21.zip":
                        if numeric_version >= 1.55:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.bin",
                                "0x210000",UPD_DIR+"/"+selected_version+"/console_image.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.partitions",
                            ]
                        else:
                            return [
                                flasher,
                                "--chip", "esp32",
                                "--port", args.port,
                                "--baud", "921600",
                                "--before", "default_reset",
                                "--after", "hard_reset",
                                "write_flash", "-z",
                                "--flash_mode", "dio",
                                "--flash_freq", "80m",
                                "--flash_size", "4MB",
                                "0xe000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.boot_app0",
                                "0x1000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.bootloader",
                                "0x10000", UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.bin",
                                "0x8000",  UPD_DIR+"/"+selected_version+"/rnode_firmware_ng21.partitions",
                            ]
                    elif fw_filename == "extracted_rnode_firmware.zip":
                        return [
                            flasher,
                            "--chip", "esp32",
                            "--port", args.port,
                            "--baud", "921600",
                            "--before", "default_reset",
                            "--after", "hard_reset",
                            "write_flash", "-z",
                            "--flash_mode", "dio",
                            "--flash_freq", "80m",
                            "--flash_size", "4MB",
                            "0x1000",  EXT_DIR+"/extracted_rnode_firmware.bootloader",
                            "0xe000",  EXT_DIR+"/extracted_rnode_firmware.boot_app0",
                            "0x8000",  EXT_DIR+"/extracted_rnode_firmware.partitions",
                            "0x10000", EXT_DIR+"/extracted_rnode_firmware.bin",
                            "0x210000",EXT_DIR+"/extracted_console_image.bin",
                        ]
                    else:
                        RNS.log("No flasher available for this board, cannot install firmware.")
                else:
                    RNS.log("")
                    RNS.log("You do not currently have the \""+flasher+"\" program installed on your system.")
                    RNS.log("Unfortunately, that means we can't proceed, since it is needed to flash your")
                    RNS.log("board. You can install it via your package manager, for example:")
                    RNS.log("")
                    RNS.log("  sudo apt install esptool")
                    RNS.log("")
                    RNS.log("Please install \""+flasher+"\" and try again.")
                    exit()

        if args.port:
            wants_fw_provision = False
            if args.flash:
                from subprocess import call
                
                if fw_filename == None:
                    fw_filename = "rnode_firmware.hex"

                if args.platform == None:
                    args.platform = ROM.PLATFORM_AVR

                if selected_version == None:
                    RNS.log("Missing parameters, cannot continue")
                    exit(68)

                if fw_filename == "extracted_rnode_firmware.zip":
                    try:
                        RNS.log("Flashing RNode firmware to device on "+args.port)
                        from subprocess import call
                        rc = get_flasher_call(args.platform, fw_filename)
                        flash_status = call(rc)
                        if flash_status == 0:
                            RNS.log("Done flashing")
                            args.rom = True
                            if args.platform == ROM.PLATFORM_ESP32:
                                wants_fw_provision = True
                                RNS.log("Waiting for ESP32 reset...")
                                time.sleep(7)
                        else:
                            exit()

                    except Exception as e:
                        RNS.log("Error while flashing")
                        RNS.log(str(e))
                        exit(1)
                
                else:
                    fw_src = UPD_DIR+"/"+selected_version+"/"
                    if os.path.isfile(fw_src+fw_filename):
                        try:
                            if fw_filename.endswith(".zip"):
                                RNS.log("Decompressing firmware...")
                                unzip_status = call(get_flasher_call("unzip", fw_filename))
                                if unzip_status == 0:
                                    RNS.log("Firmware decompressed")
                                else:
                                    RNS.log("Could not extract firmware from downloaded zip file")
                                    exit()

                            RNS.log("Flashing RNode firmware to device on "+args.port)
                            from subprocess import call
                            rc = get_flasher_call(args.platform, fw_filename)
                            flash_status = call(rc)
                            if flash_status == 0:
                                RNS.log("Done flashing")
                                args.rom = True
                                if args.platform == ROM.PLATFORM_ESP32:
                                    wants_fw_provision = True
                                    RNS.log("Waiting for ESP32 reset...")
                                    time.sleep(7)
                            else:
                                exit()

                        except Exception as e:
                            RNS.log("Error while flashing")
                            RNS.log(str(e))
                            exit(1)
                    else:
                        RNS.log("Firmware file not found")
                        exit()

            RNS.log("Opening serial port "+args.port+"...")
            try:
                rnode_port = args.port
                rnode_serial = rnode_open_serial(rnode_port)
            except Exception as e:
                RNS.log("Could not open the specified serial port. The contained exception was:")
                RNS.log(str(e))
                exit()

            rnode = RNode(rnode_serial)
            thread = threading.Thread(target=rnode.readLoop, daemon=True).start()

            try:
                rnode.device_probe()
            except Exception as e:
                RNS.log("Serial port opened, but RNode did not respond. Is a valid firmware installed?")
                print(e)
                exit()

            if rnode.detected:
                if rnode.platform == None or rnode.mcu == None:
                    rnode.platform = ROM.PLATFORM_AVR
                    rnode.mcu = ROM.MCU_1284P


            if args.eeprom_wipe:
                RNS.log("WARNING: EEPROM is being wiped! Power down device NOW if you do not want this!")
                rnode.wipe_eeprom()
                exit()

            RNS.log("Reading EEPROM...")
            rnode.download_eeprom()

            if rnode.provisioned:
                if rnode.model != ROM.MODEL_FF:
                    fw_filename = models[rnode.model][4]
                else:
                    if args.use_extracted:
                        fw_filename = "extracted_rnode_firmware.zip"
                    else:
                        if rnode.platform == ROM.PLATFORM_AVR:
                            if rnode.mcu == ROM.MCU_1284P:
                                fw_filename = "rnode_firmware.hex"
                            elif rnode.mcu == ROM.MCU_2560:
                                fw_filename = "rnode_firmware_m2560.hex"
                        elif rnode.platform == ROM.PLATFORM_ESP32:
                            if rnode.board == ROM.BOARD_HUZZAH32:
                                fw_filename = "rnode_firmware_featheresp32.zip"
                            elif rnode.board == ROM.BOARD_GENERIC_ESP32:
                                fw_filename = "rnode_firmware_esp32_generic.zip"
                            else:
                                fw_filename = None
                                if args.update:
                                    RNS.log("ERROR: No firmware found for this board. Cannot update.")
                                    exit()

            if args.update:
                if not rnode.provisioned:
                    RNS.log("Device not provisioned. Cannot update device firmware.")
                    exit(1)

                if args.use_extracted:
                    fw_filename = "extracted_rnode_firmware.zip"

                from subprocess import call

                try:
                    RNS.log("Checking firmware file availability...")
                    fw_file_ensured = False
                    if selected_version == None:
                        ensure_firmware_file(fw_filename)
                        fw_file_ensured = True

                    if not force_update:
                        if rnode.version == selected_version:
                            if args.fw_version != None:
                                RNS.log("Specified firmware version ("+selected_version+") is already installed on this device")
                                RNS.log("Override with -U option to install anyway")
                                exit(0)
                            else:
                                RNS.log("Latest firmware version ("+selected_version+") is already installed on this device")
                                RNS.log("Override with -U option to install anyway")
                                exit(0)

                        if rnode.version > selected_version:
                            if args.fw_version != None:
                                RNS.log("Specified firmware version ("+selected_version+") is older than firmware already installed on this device")
                                RNS.log("Override with -U option to install anyway")
                                exit(0)
                            else:
                                RNS.log("Latest firmware version ("+selected_version+") is older than firmware already installed on this device")
                                RNS.log("Override with -U option to install anyway")
                                exit(0)

                    if not fw_file_ensured and selected_version != None:
                        ensure_firmware_file(fw_filename)

                    if fw_filename.endswith(".zip") and not fw_filename == "extracted_rnode_firmware.zip":
                        RNS.log("Extracting firmware...")
                        unzip_status = call(get_flasher_call("unzip", fw_filename))
                        if unzip_status == 0:
                            RNS.log("Firmware extracted")
                        else:
                            RNS.log("Could not extract firmware from downloaded zip file")
                            exit()

                except Exception as e:
                    RNS.log("Could not obtain firmware package for your board")
                    RNS.log("The contained exception was: "+str(e))
                    exit()

                if fw_filename == "extracted_rnode_firmware.zip":
                    update_full_path = EXT_DIR+"/extracted_rnode_firmware.version"
                else:
                    update_full_path = UPD_DIR+"/"+selected_version+"/"+fw_filename
                if os.path.isfile(update_full_path): 
                    try:
                        args.info = False
                        RNS.log("Updating RNode firmware for device on "+args.port)
                        if fw_filename == "extracted_rnode_firmware.zip":
                            vf = open(update_full_path, "rb")
                            release_info = vf.read().decode("utf-8").strip()
                            partition_hash = bytes.fromhex(release_info.split()[1])
                            vf.close()
                        else:
                            partition_filename = fw_filename.replace(".zip", ".bin")
                            partition_hash = get_partition_hash(UPD_DIR+"/"+selected_version+"/"+partition_filename)
                        if partition_hash != None:
                            rnode.set_firmware_hash(partition_hash)
                            rnode.indicate_firmware_update()
                            sleep(1)

                        rnode.disconnect()
                        flash_status = call(get_flasher_call(rnode.platform, fw_filename))
                        if flash_status == 0:
                            RNS.log("Flashing new firmware completed")
                            RNS.log("Opening serial port "+args.port+"...")
                            try:
                                rnode_port = args.port
                                rnode_serial = rnode_open_serial(rnode_port)
                            except Exception as e:
                                RNS.log("Could not open the specified serial port. The contained exception was:")
                                RNS.log(str(e))
                                exit()

                            rnode = RNode(rnode_serial)
                            thread = threading.Thread(target=rnode.readLoop, daemon=True).start()

                            try:
                                rnode.device_probe()
                            except Exception as e:
                                RNS.log("Serial port opened, but RNode did not respond. Is a valid firmware installed?")
                                print(e)
                                exit()

                            if rnode.detected:
                                if rnode.platform == None or rnode.mcu == None:
                                    rnode.platform = ROM.PLATFORM_AVR
                                    rnode.mcu = ROM.MCU_1284P

                                RNS.log("Reading EEPROM...")
                                rnode.download_eeprom()

                                if rnode.provisioned:
                                    if rnode.model != ROM.MODEL_FF:
                                        fw_filename = models[rnode.model][4]
                                    else:
                                        fw_filename = None
                                    args.info = True
                                    if partition_hash != None:
                                        rnode.set_firmware_hash(partition_hash)

                            if args.info:
                                RNS.log("")
                                RNS.log("Firmware update completed successfully")
                        else:
                            RNS.log("An error occurred while flashing the new firmware, exiting now.")
                            exit()

                    except Exception as e:
                        RNS.log("Error while updating firmware")
                        RNS.log(str(e))
                else:
                    RNS.log("Firmware update file not found")
                    exit()

            if args.eeprom_dump:
                RNS.log("EEPROM contents:")
                RNS.log(RNS.hexrep(rnode.eeprom))
                exit()

            if args.eeprom_backup:
                try:
                    timestamp = time.time()
                    filename = str(time.strftime("%Y-%m-%d_%H-%M-%S"))
                    path = "./eeprom/"+filename+".eeprom"
                    file = open(path, "wb")
                    file.write(rnode.eeprom)
                    file.close()
                    RNS.log("EEPROM backup written to: "+path)
                except Exception as e:
                    RNS.log("EEPROM was successfully downloaded from device,")
                    RNS.log("but file could not be written to disk.")
                exit()

            if args.bluetooth_on:
                RNS.log("Enabling Bluetooth...")
                rnode.enable_bluetooth()
                rnode.leave()

            if args.bluetooth_off:
                RNS.log("Disabling Bluetooth...")
                rnode.disable_bluetooth()
                rnode.leave()

            if args.bluetooth_pair:
                RNS.log("Putting device into Bluetooth pairing mode. Press enter to exit when done.")
                rnode.bluetooth_pair()
                input()
                rnode.leave()

            if args.info:
                if rnode.provisioned:
                    timestamp = struct.unpack(">I", rnode.made)[0]
                    timestring = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    sigstring = "Unverified"
                    if rnode.signature_valid:
                        if rnode.locally_signed:
                            sigstring = "Validated - Local signature"
                        else:
                            sigstring = "Genuine board, vendor is "+rnode.vendor

                    if rnode.board != None:
                        board_string = ":"+bytes([rnode.board]).hex()
                    else:
                        board_string = ""

                    RNS.log("")
                    RNS.log("Device info:")
                    RNS.log("\tProduct            : "+products[rnode.product]+" "+models[rnode.model][3]+" ("+bytes([rnode.product]).hex()+":"+bytes([rnode.model]).hex()+board_string+")")
                    RNS.log("\tDevice signature   : "+sigstring)
                    RNS.log("\tFirmware version   : "+rnode.version)
                    RNS.log("\tHardware revision  : "+str(int(rnode.hw_rev)))
                    RNS.log("\tSerial number      : "+RNS.hexrep(rnode.serialno))
                    RNS.log("\tFrequency range    : "+str(rnode.min_freq/1e6)+" MHz - "+str(rnode.max_freq/1e6)+" MHz")
                    RNS.log("\tMax TX power       : "+str(rnode.max_output)+" dBm")
                    RNS.log("\tManufactured       : "+timestring)

                    if rnode.configured:
                        rnode.bandwidth = rnode.conf_bandwidth
                        rnode.r_bandwidth = rnode.conf_bandwidth
                        rnode.sf = rnode.conf_sf
                        rnode.r_sf = rnode.conf_sf
                        rnode.cr = rnode.conf_cr
                        rnode.r_cr = rnode.conf_cr
                        rnode.updateBitrate()
                        txp_mw = round(pow(10, (rnode.conf_txpower/10)), 3)
                        RNS.log("");
                        RNS.log("\tDevice mode        : TNC")
                        RNS.log("\t  Frequency        : "+str((rnode.conf_frequency/1000000.0))+" MHz")
                        RNS.log("\t  Bandwidth        : "+str(rnode.conf_bandwidth/1000.0)+" KHz")
                        RNS.log("\t  TX power         : "+str(rnode.conf_txpower)+" dBm ("+str(txp_mw)+" mW)")
                        RNS.log("\t  Spreading factor : "+str(rnode.conf_sf))
                        RNS.log("\t  Coding rate      : "+str(rnode.conf_cr))
                        RNS.log("\t  On-air bitrate   : "+str(rnode.bitrate_kbps)+" kbps")
                    else:
                        RNS.log("\tDevice mode        : Normal (host-controlled)")

                    print("")
                    rnode.disconnect()
                    exit()

                else:
                    RNS.log("EEPROM is invalid, no further information available")
                    exit()

            if args.rom:
                if rnode.provisioned and not args.autoinstall:
                    RNS.log("EEPROM bootstrap was requested, but a valid EEPROM was already present.")
                    RNS.log("No changes are being made.")
                    exit()

                else:
                    if rnode.signature_valid:
                        RNS.log("EEPROM bootstrap was requested, but a valid EEPROM was already present.")
                        RNS.log("No changes are being made.")
                        exit()
                    else:
                        if args.autoinstall:
                            RNS.log("Clearing old EEPROM, this will take about 15 seconds...")
                            rnode.wipe_eeprom()
                            
                        if rnode.platform == ROM.PLATFORM_ESP32:
                            RNS.log("Waiting for ESP32 reset...")
                            time.sleep(6)
                        else:
                            time.sleep(3)

                    counter = None
                    counter_path = FWD_DIR+"/serial.counter"
                    try:
                        if os.path.isfile(counter_path):
                            file = open(counter_path, "r")
                            counter_str = file.read()
                            counter = int(counter_str)
                            file.close()
                        else:
                            counter = 0
                    except Exception as e:
                        RNS.log("Could not create device serial number, exiting")
                        RNS.log(str(e))
                        exit()

                    serialno = counter+1
                    model = None
                    hwrev = None
                    if args.product != None:
                        if args.product == "03":
                            mapped_product = ROM.PRODUCT_RNODE
                        if args.product == "f0":
                            mapped_product = ROM.PRODUCT_HMBRW
                        if args.product == "e0":
                            mapped_product = ROM.PRODUCT_TBEAM

                    if mapped_model != None:
                        model = mapped_model
                    else:
                        if args.model == "a4":
                            model = ROM.MODEL_A4
                        elif args.model == "a9":
                            model = ROM.MODEL_A9
                        elif args.model == "e4":
                            model = ROM.MODEL_E4
                        elif args.model == "e9":
                            model = ROM.MODEL_E9
                        elif args.model == "ff":
                            model = ROM.MODEL_FF


                    if args.hwrev != None and (args.hwrev > 0 and args.hwrev < 256):
                        hwrev = chr(args.hwrev)

                    if serialno > 0 and model != None and hwrev != None:
                        try:
                            from cryptography.hazmat.primitives import hashes
                            from cryptography.hazmat.backends import default_backend

                            timestamp = int(time.time())
                            time_bytes = struct.pack(">I", timestamp)
                            serial_bytes = struct.pack(">I", serialno)
                            file = open(counter_path, "w")
                            file.write(str(serialno))
                            file.close()

                            info_chunk  = b"" + bytes([mapped_product, model, ord(hwrev)])
                            info_chunk += serial_bytes
                            info_chunk += time_bytes
                            digest = hashes.Hash(hashes.MD5(), backend=default_backend())
                            digest.update(info_chunk)
                            checksum = digest.finalize()

                            RNS.log("Loading signing key...")
                            signature = None
                            key_path = FWD_DIR+"/signing.key"
                            if os.path.isfile(key_path):
                                try:
                                    file = open(key_path, "rb")
                                    private_bytes = file.read()
                                    file.close()
                                    private_key = serialization.load_der_private_key(
                                        private_bytes,
                                        password=None,
                                        backend=default_backend()
                                    )
                                    public_key = private_key.public_key()
                                    public_bytes = public_key.public_bytes(
                                        encoding=serialization.Encoding.DER,
                                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                                    )
                                    signature = private_key.sign(
                                        checksum,
                                        padding.PSS(
                                            mgf=padding.MGF1(hashes.SHA256()),
                                            salt_length=padding.PSS.MAX_LENGTH
                                        ),
                                        hashes.SHA256()
                                    )
                                except Exception as e:
                                    RNS.log("Error while signing EEPROM")
                                    RNS.log(str(e))
                            else:
                                RNS.log("No signing key found")
                                exit()


                            RNS.log("Bootstrapping device EEPROM...")

                            rnode.write_eeprom(ROM.ADDR_PRODUCT, mapped_product)
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_MODEL, model)
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_HW_REV, ord(hwrev))
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_SERIAL, serial_bytes[0])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_SERIAL+1, serial_bytes[1])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_SERIAL+2, serial_bytes[2])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_SERIAL+3, serial_bytes[3])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_MADE, time_bytes[0])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_MADE+1, time_bytes[1])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_MADE+2, time_bytes[2])
                            time.sleep(0.006)
                            rnode.write_eeprom(ROM.ADDR_MADE+3, time_bytes[3])
                            time.sleep(0.006)

                            for i in range(0,16):
                                rnode.write_eeprom(ROM.ADDR_CHKSUM+i, checksum[i])
                                time.sleep(0.006)

                            for i in range(0,128):
                                rnode.write_eeprom(ROM.ADDR_SIGNATURE+i, signature[i])
                                time.sleep(0.006)

                            rnode.write_eeprom(ROM.ADDR_INFO_LOCK, ROM.INFO_LOCK_BYTE)

                            RNS.log("EEPROM written! Validating...")

                            if wants_fw_provision:
                                partition_hash = None

                                if fw_filename == "extracted_rnode_firmware.zip":
                                    update_full_path = EXT_DIR+"/extracted_rnode_firmware.version"
                                    vf = open(update_full_path, "rb")
                                    release_info = vf.read().decode("utf-8").strip()
                                    partition_hash = bytes.fromhex(release_info.split()[1])
                                    vf.close()
                                else:
                                    partition_filename = fw_filename.replace(".zip", ".bin")
                                    partition_hash = get_partition_hash(UPD_DIR+"/"+selected_version+"/"+partition_filename)

                                if partition_hash != None:
                                    rnode.set_firmware_hash(partition_hash)

                            rnode.hard_reset()
                            if rnode.platform == ROM.PLATFORM_ESP32:
                                RNS.log("Waiting for ESP32 reset...")
                                time.sleep(6.5)

                            rnode.download_eeprom()
                            if rnode.provisioned:
                                RNS.log("EEPROM Bootstrapping successful!")
                                rnode.hard_reset()
                                if args.autoinstall:
                                    print("")
                                    print("RNode Firmware autoinstallation complete!")
                                    print("")
                                    print("To use your device with Reticulum, read the documetation at:")
                                    print("")
                                    print("https://markqvist.github.io/Reticulum/manual/gettingstartedfast.html")
                                    print("")
                                    print("* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *")
                                    print("                              Important!            ")
                                    print("")
                                    print("ESP32-based RNodes are created with the RNode Bootstrap Console on-board.")
                                    print("")
                                    print("This repository is hosted directly on the RNode, and contains a wealth of")
                                    print("information, software and tools.")
                                    print("")
                                    print("The RNode Bootstrap Console also contains everything needed to build")
                                    print("and replicate RNodes, including detailed build recipes, 3D-printable")
                                    print("cases, and copies of the source code for both the RNode Firmware,")
                                    print("Reticulum and other utilities.")
                                    print("")
                                    print("To activate the RNode Bootstrap Console, power up your RNode and press")
                                    print("the reset button twice with a one second interval. The RNode will now")
                                    print("reboot into console mode, and activate a WiFi access point for you to")
                                    print("connect to. The console is then reachable at: http://10.0.0.1")
                                    print("")
                                    print("* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *")
                                    print("")
                                    print("Thank you for using this utility! Please help the project by")
                                    print("contributing code and reporting bugs, or by donating!")
                                    print("")
                                    print("Your contributions and donations directly further the realisation")
                                    print("of truly open, free and resilient communications systems.")
                                    print("")
                                    print_donation_block()
                                    print("")
                                try:
                                    os.makedirs(FWD_DIR+"/device_db/", exist_ok=True)
                                    file = open(FWD_DIR+"/device_db/"+serial_bytes.hex(), "wb")
                                    written = file.write(rnode.eeprom)
                                    file.close()
                                except Exception as e:
                                    RNS.log("WARNING: Could not backup device EEPROM to disk")
                                exit()
                            else:
                                RNS.log("EEPROM was written, but validation failed. Check your settings.")
                                exit()
                        except Exception as e:
                            RNS.log("An error occurred while writing EEPROM. The contained exception was:")
                            RNS.log(str(e))
                            raise e

                    else:
                        RNS.log("Invalid data specified, cancelling EEPROM write")
                        exit()

            if args.sign:
                if rnode.provisioned:
                    try:
                        device_signer = RNS.Identity.from_file(FWD_DIR+"/device.key")
                    except Exception as e:
                        RNS.log("Could not load device signing key")

                    if rnode.device_hash == None:
                        RNS.log("No device hash present, skipping device signing")
                    else:
                        if device_signer == None:
                            RNS.log("No device signer loaded, cannot sign device")
                            exit(78)
                        else:
                            new_device_signature = device_signer.sign(rnode.device_hash)
                            rnode.store_signature(new_device_signature)
                            RNS.log("Device signed")
                else:
                    RNS.log("This device has not been provisioned yet, cannot create device signature")
                    exit(79)

            if args.firmware_hash != None:
                if rnode.provisioned:
                    try:
                        hash_data = bytes.fromhex(args.firmware_hash)
                        if len(hash_data) != 32:
                            raise ValueError("Incorrect hash length")

                        rnode.set_firmware_hash(hash_data)
                        RNS.log("Firmware hash set")
                    except Exception as e:
                        RNS.log("The provided value was not a valid SHA256 hash")
                        exit(78)

                else:
                    RNS.log("This device has not been provisioned yet, cannot set firmware hash")
                    exit(77)

            if rnode.provisioned:
                if args.normal:
                    rnode.setNormalMode()
                    RNS.log("Device set to normal (host-controlled) operating mode")
                    exit()
                if args.tnc:
                    if not (args.freq and args.bw and args.txp and args.sf and args.cr):
                        RNS.log("Please input startup configuration:")

                    print("")
                    if args.freq:
                        rnode.frequency = args.freq
                    else:
                        print("Frequency in Hz:\t", end="")
                        rnode.frequency = int(input())


                    if args.bw:
                        rnode.bandwidth = args.bw
                    else:
                        print("Bandwidth in Hz:\t", end="")
                        rnode.bandwidth = int(input())

                    if args.txp != None and (args.txp >= 0 and args.txp <= 17):
                        rnode.txpower = args.txp
                    else:
                        print("TX Power in dBm:\t", end="")
                        rnode.txpower = int(input())

                    if args.sf:
                        rnode.sf = args.sf
                    else:
                        print("Spreading factor:\t", end="")
                        rnode.sf = int(input())

                    if args.cr:
                        rnode.cr = args.cr
                    else:
                        print("Coding rate:\t\t", end="")
                        rnode.cr = int(input())

                    print("")

                    rnode.initRadio()
                    sleep(0.5)
                    rnode.setTNCMode()
                    RNS.log("Device set to TNC operating mode")
                    sleep(1.0)

                    exit()
            else:
                RNS.log("This device contains a valid firmware, but EEPROM is invalid.")
                RNS.log("Probably the device has not been initialised, or the EEPROM has been erased.")
                RNS.log("Please correctly initialise the device and try again!")

        else:
            print("")
            parser.print_help()
            print("")
            exit()


    except KeyboardInterrupt:
        print("")
        exit()

def extract_recovery_esptool():
    if not os.path.isfile(RT_PATH):
        try:
            RNS.log("Extracting recovery ESP-Tool...")
            import base64, gzip
            recovery_esptool = "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"
            out = open(RT_PATH, "wb")
            out.write("#!/usr/bin/env python3\n\n".encode("utf-8")+gzip.decompress(base64.b64decode(recovery_esptool)))
            out.close()
        except Exception as e:
            RNS.log("Error: Could not extract recovery ESP-Tool. The contained exception was:")
            RNS.log(str(e))
            exit(181)

if __name__ == "__main__":
    main()