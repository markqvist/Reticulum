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
    CMD_DETECT      = 0x08
    CMD_IMPLICIT    = 0x09
    CMD_LEAVE       = 0x0A
    CMD_READY       = 0x0F
    CMD_STAT_RX     = 0x21
    CMD_STAT_TX     = 0x22
    CMD_STAT_RSSI   = 0x23
    CMD_STAT_SNR    = 0x24
    CMD_BLINK       = 0x30
    CMD_RANDOM      = 0x40
    CMD_FB_EXT      = 0x41
    CMD_FB_READ     = 0x42
    CMD_FB_WRITE    = 0x43
    CMD_FB_READL    = 0x44
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
    ERROR_INVALID_FIRMWARE = 0x10

    PLATFORM_AVR   = 0x90
    PLATFORM_ESP32 = 0x80

    @staticmethod
    def escape(data):
        data = data.replace(bytes([0xdb]), bytes([0xdb, 0xdd]))
        data = data.replace(bytes([0xc0]), bytes([0xdb, 0xdc]))
        return data

class AndroidBluetoothManager():
    def __init__(self, owner, target_device_name = None, target_device_address = None):
        from jnius import autoclass
        self.owner = owner
        self.connected = False
        self.target_device_name = target_device_name
        self.target_device_address = target_device_address
        self.potential_remote_devices = []
        self.rfcomm_socket = None
        self.connected_device = None
        self.connection_failed = False
        self.bt_adapter = autoclass('android.bluetooth.BluetoothAdapter')
        self.bt_device  = autoclass('android.bluetooth.BluetoothDevice')
        self.bt_socket  = autoclass('android.bluetooth.BluetoothSocket')
        self.bt_rfcomm_service_record = autoclass('java.util.UUID').fromString("00001101-0000-1000-8000-00805F9B34FB")
        self.buffered_input_stream    = autoclass('java.io.BufferedInputStream')

    def connect(self, device_address=None):
        self.rfcomm_socket = self.remote_device.createRfcommSocketToServiceRecord(self.bt_rfcomm_service_record)

    def bt_enabled(self):
        return self.bt_adapter.getDefaultAdapter().isEnabled()

    def get_paired_devices(self):
        if self.bt_enabled():
            return self.bt_adapter.getDefaultAdapter().getBondedDevices()
        else:
            RNS.log("Could not query paired devices, Bluetooth is disabled", RNS.LOG_DEBUG)
            return []

    def get_potential_devices(self):
        potential_devices = []
        for device in self.get_paired_devices():
            if self.target_device_address != None:
                if str(device.getAddress()).replace(":", "").lower() == str(self.target_device_address).replace(":", "").lower():
                    if self.target_device_name == None:
                        potential_devices.append(device)
                    else:
                        if device.getName().lower() == self.target_device_name.lower():
                            potential_devices.append(device)

            elif self.target_device_name != None:
                if device.getName().lower() == self.target_device_name.lower():
                    potential_devices.append(device)

            else:
                if device.getName().lower().startswith("rnode "):
                    potential_devices.append(device)

        return potential_devices

    def connect_any_device(self):
        if (self.rfcomm_socket != None and not self.rfcomm_socket.isConnected()) or self.rfcomm_socket == None:
            self.connection_failed = False
            if len(self.potential_remote_devices) == 0:
                self.potential_remote_devices = self.get_potential_devices()
                if len(self.potential_remote_devices) == 0:
                    RNS.log("No suitable bluetooth devices available, can't connect", RNS.LOG_DEBUG)
                    return

            while not self.connected and len(self.potential_remote_devices) > 0:
                device = self.potential_remote_devices.pop()
                try:
                    self.rfcomm_socket = device.createRfcommSocketToServiceRecord(self.bt_rfcomm_service_record)
                    if self.rfcomm_socket == None:
                        raise IOError("Bluetooth stack returned no socket object")
                    else:
                        if not self.rfcomm_socket.isConnected():
                            try:
                                self.rfcomm_socket.connect()
                                self.rfcomm_reader = self.buffered_input_stream(self.rfcomm_socket.getInputStream(), 1024)
                                self.rfcomm_writer = self.rfcomm_socket.getOutputStream()
                                self.connected = True
                                self.connected_device = device
                                RNS.log("Bluetooth device "+str(self.connected_device.getName())+" "+str(self.connected_device.getAddress())+" connected.")
                            except Exception as e:
                                raise IOError("The Bluetooth RFcomm socket could not be connected: "+str(e))

                except Exception as e:
                    RNS.log("Could not create and connect Bluetooth RFcomm socket for "+str(device.getName())+" "+str(device.getAddress()), RNS.LOG_ERROR)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

    def close(self):
        if self.connected:
            if self.rfcomm_reader != None:
                self.rfcomm_reader.close()
                self.rfcomm_reader = None
            
            if self.rfcomm_writer != None:
                self.rfcomm_writer.close()
                self.rfcomm_writer = None

            if self.rfcomm_socket != None:
                self.rfcomm_socket.close()

            self.connected = False
            self.connected_device = None
            self.potential_remote_devices = []


    def read(self, len = None):
        if self.connection_failed:
            raise IOError("Bluetooth connection failed")
        else:
            if self.connected and self.rfcomm_reader != None:
                available = self.rfcomm_reader.available()
                if available > 0:
                    if hasattr(self.rfcomm_reader, "readNBytes"):
                        return self.rfcomm_reader.readNBytes(available)
                    else:
                        # Compatibility mode for older android versions lacking readNBytes
                        rb = self.rfcomm_reader.read().to_bytes(1, "big")
                        return rb
                else:
                    return bytes([])
            else:
                raise IOError("No RFcomm socket available")

    def write(self, data):
        try:
            self.rfcomm_writer.write(data)
            self.rfcomm_writer.flush()
            return len(data)
        except Exception as e:
            RNS.log("Bluetooth connection failed for "+str(self), RNS.LOG_ERROR)
            self.connection_failed = True
            return 0


class RNodeInterface(Interface):
    MAX_CHUNK = 32768

    FREQ_MIN = 137000000
    FREQ_MAX = 1020000000

    RSSI_OFFSET = 157

    CALLSIGN_MAX_LEN    = 32

    REQUIRED_FW_VER_MAJ = 1
    REQUIRED_FW_VER_MIN = 52

    RECONNECT_WAIT = 5
    PORT_IO_TIMEOUT = 3

    @classmethod
    def bluetooth_control(device_serial = None, port = None, enable_bluetooth = False, disable_bluetooth = False, pairing_mode = False):
        if (port != None or device_serial != None) and (enable_bluetooth or disable_bluetooth or pairing_mode):
            serial = None
            bluetooth_state = None
            if pairing_mode:
                bluetooth_state = 0x01
            elif enable_bluetooth:
                bluetooth_state = 0x01
            elif disable_bluetooth:
                bluetooth_state = 0x00

            if port != None:
                RNS.log("Opening serial port "+port+"...")
                # Get device parameters
                from usb4a import usb
                device = usb.get_usb_device(port)
                if device:
                    vid = device.getVendorId()
                    pid = device.getProductId()

                    # Driver overrides for speficic chips
                    from usbserial4a import serial4a as pyserial
                    proxy = pyserial.get_serial_port
                    if vid == 0x1A86 and pid == 0x55D4:
                        # Force CDC driver for Qinheng CH34x
                        RNS.log("Using CDC driver for "+RNS.hexrep(vid)+":"+RNS.hexrep(pid), RNS.LOG_DEBUG)
                        from usbserial4a.cdcacmserial4a import CdcAcmSerial
                        proxy = CdcAcmSerial

                    serial = proxy(
                        port,
                        baudrate = 115200,
                        bytesize = 8,
                        parity = "N",
                        stopbits = 1,
                        xonxoff = False,
                        rtscts = False,
                        timeout = None,
                        inter_byte_timeout = None,
                        # write_timeout = wtimeout,
                        dsrdtr = False,
                    )

                    if vid == 0x0403:
                        # Hardware parameters for FTDI devices @ 115200 baud
                        serial.DEFAULT_READ_BUFFER_SIZE = 16 * 1024
                        serial.USB_READ_TIMEOUT_MILLIS = 100
                        serial.timeout = 0.1
                    elif vid == 0x10C4:
                        # Hardware parameters for SiLabs CP210x @ 115200 baud
                        serial.DEFAULT_READ_BUFFER_SIZE = 64
                        serial.USB_READ_TIMEOUT_MILLIS = 12
                        serial.timeout = 0.012
                    elif vid == 0x1A86 and pid == 0x55D4:
                        # Hardware parameters for Qinheng CH34x @ 115200 baud
                        serial.DEFAULT_READ_BUFFER_SIZE = 64
                        serial.USB_READ_TIMEOUT_MILLIS = 12
                        serial.timeout = 0.1
                    else:
                        # Default values
                        serial.DEFAULT_READ_BUFFER_SIZE = 1 * 1024
                        serial.USB_READ_TIMEOUT_MILLIS = 100
                        serial.timeout = 0.1

            elif device_serial != None:
                serial = device_serial

            if serial != None:
                if serial.is_open:
                    kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, bluetooth_state, KISS.FEND])
                    serial.write(kiss_command)
                    if pairing_mode:
                        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x02, KISS.FEND])
                        serial.write(kiss_command)

            if port != None:
                serial.close()


    def __init__(
        self, owner, name, port, frequency = None, bandwidth = None, txpower = None,
        sf = None, cr = None, flow_control = False, id_interval = None,
        allow_bluetooth = False, target_device_name = None,
        target_device_address = None, id_callsign = None):
        import importlib
        if RNS.vendor.platformutils.is_android():
            self.on_android  = True
            if importlib.util.find_spec('usbserial4a') != None:
                if importlib.util.find_spec('jnius') == None:
                    RNS.log("Could not load jnius API wrapper for Android, RNode interface cannot be created.", RNS.LOG_CRITICAL)
                    RNS.log("This probably means you are trying to use an USB-based interface from within Termux or similar.", RNS.LOG_CRITICAL)
                    RNS.log("This is currently not possible, due to this environment limiting access to the native Android APIs.", RNS.LOG_CRITICAL)
                    RNS.panic()

                from usbserial4a import serial4a as serial
                self.parity = "N"

                self.bt_target_device_name = target_device_name
                self.bt_target_device_address = target_device_address
                if allow_bluetooth:
                    self.bt_manager = AndroidBluetoothManager(
                        owner = self,
                        target_device_name = self.bt_target_device_name,
                        target_device_address = self.bt_target_device_address
                    )

                else:
                    self.bt_manager = None
            
            else:
                RNS.log("Could not load USB serial module for Android, RNode interface cannot be created.", RNS.LOG_CRITICAL)
                RNS.log("You can install this module by issuing: pip install usbserial4a", RNS.LOG_CRITICAL)
                RNS.panic()
        else:
            raise SystemError("Android-specific interface was used on non-Android OS")

        self.rxb = 0
        self.txb = 0

        self.HW_MTU = 508
        
        self.pyserial    = serial
        self.serial      = None
        self.owner       = owner
        self.name        = name
        self.port        = port
        self.speed       = 115200
        self.databits    = 8
        self.stopbits    = 1
        self.timeout     = 150
        self.online      = False
        self.hw_errors   = []
        self.allow_bluetooth = allow_bluetooth

        self.frequency   = frequency
        self.bandwidth   = bandwidth
        self.txpower     = txpower
        self.sf          = sf
        self.cr          = cr
        self.state       = KISS.RADIO_STATE_OFF
        self.bitrate     = 0
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
        self.r_random    = None

        self.packet_queue    = []
        self.flow_control    = flow_control
        self.interface_ready = False
        self.announce_rate_target = None
        self.last_port_io = 0
        self.port_io_timeout = RNodeInterface.PORT_IO_TIMEOUT
        self.last_imagedata = None

        self.validcfg  = True
        if (self.frequency < RNodeInterface.FREQ_MIN or self.frequency > RNodeInterface.FREQ_MAX):
            RNS.log("Invalid frequency configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.txpower < 0 or self.txpower > 17):
            RNS.log("Invalid TX power configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.bandwidth < 7800 or self.bandwidth > 500000):
            RNS.log("Invalid bandwidth configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.sf < 7 or self.sf > 12):
            RNS.log("Invalid spreading factor configured for "+str(self), RNS.LOG_ERROR)
            self.validcfg = False

        if (self.cr < 5 or self.cr > 8):
            RNS.log("Invalid coding rate configured for "+str(self), RNS.LOG_ERROR)
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

            if self.serial != None:
                if self.serial.is_open:
                    self.configure_device()
                else:
                    raise IOError("Could not open serial port")
            elif self.bt_manager != None:
                if self.bt_manager.connected:
                    self.configure_device()
                else:
                    raise IOError("Could not connect to any Bluetooth devices")
            else:
                raise IOError("Neither serial port nor Bluetooth devices available")

        except Exception as e:
            RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
            if len(self.hw_errors) == 0:
                RNS.log("Reticulum will attempt to bring up this interface periodically", RNS.LOG_ERROR)
                thread = threading.Thread(target=self.reconnect_port)
                thread.daemon = True
                thread.start()


    def read_mux(self, len=None):
        if self.serial != None:
            return self.serial.read()
        elif self.bt_manager != None:
            return self.bt_manager.read()
        else:
            raise IOError("No ports available for reading")

    def write_mux(self, data):
        if self.serial != None:
            written = self.serial.write(data)
            self.last_port_io = time.time()
            return written
        elif self.bt_manager != None:
            written = self.bt_manager.write(data)
            if (written == len(data)):
                self.last_port_io = time.time()
            return written
        else:
            raise IOError("No ports available for writing")

    def open_port(self):
        if self.port != None:
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

        elif self.allow_bluetooth:
            if self.bt_manager == None:
                self.bt_manager = AndroidBluetoothManager(
                    owner = self,
                    target_device_name = self.bt_target_device_name,
                    target_device_address = self.bt_target_device_address
                )

            if self.bt_manager != None:
                self.bt_manager.connect_any_device()


    def configure_device(self):
        sleep(2.0)
        thread = threading.Thread(target=self.readLoop)
        thread.daemon = True
        thread.start()

        self.detect()
        sleep(0.5)

        if not self.detected:
            raise IOError("Could not detect device")
        else:
            if self.platform == KISS.PLATFORM_ESP32:
                self.display = True

        if not self.firmware_ok:
            raise IOError("Invalid device firmware")

        if self.serial != None and self.port != None:
            RNS.log("Serial port "+self.port+" is now open")
        if self.bt_manager != None and self.bt_manager.connected:
            RNS.log("Bluetooth connection to RNode now open")

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
            
            if self.serial != None:
                self.serial.close()
            if self.bt_manager != None:
                self.bt_manager.close()

            raise IOError("RNode interface did not pass configuration validation")
            

    def initRadio(self):
        self.setFrequency()
        time.sleep(0.15)

        self.setBandwidth()
        time.sleep(0.15)
        
        self.setTXPower()
        time.sleep(0.15)
        
        self.setSpreadingFactor()
        time.sleep(0.15)
        
        self.setCodingRate()
        time.sleep(0.15)
        
        self.setRadioState(KISS.RADIO_STATE_ON)
        time.sleep(0.15)

    def detect(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_DETECT, KISS.DETECT_REQ, KISS.FEND, KISS.CMD_FW_VERSION, 0x00, KISS.FEND, KISS.CMD_PLATFORM, 0x00, KISS.FEND, KISS.CMD_MCU, 0x00, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while detecting hardware for "+str(self))

    def leave(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_LEAVE, 0xFF, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending host left command to device")
    
    def enable_bluetooth(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x01, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending bluetooth enable command to device")

    def disable_bluetooth(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x00, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending bluetooth disable command to device")

    def bluetooth_pair(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_BT_CTRL, 0x02, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending bluetooth pair command to device")

    def enable_external_framebuffer(self):
        if self.display != None:
            kiss_command = bytes([KISS.FEND, KISS.CMD_FB_EXT, 0x01, KISS.FEND])
            written = self.write_mux(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while enabling external framebuffer on device")

    def disable_external_framebuffer(self):
        if self.display != None:
            kiss_command = bytes([KISS.FEND, KISS.CMD_FB_EXT, 0x00, KISS.FEND])
            written = self.write_mux(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while disabling external framebuffer on device")

    FB_PIXEL_WIDTH     = 64
    FB_BITS_PER_PIXEL  = 1
    FB_PIXELS_PER_BYTE = 8//FB_BITS_PER_PIXEL
    FB_BYTES_PER_LINE  = FB_PIXEL_WIDTH//FB_PIXELS_PER_BYTE
    def display_image(self, imagedata):
        self.last_imagedata = imagedata
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
            
            written = self.write_mux(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while writing framebuffer data device")

    def hard_reset(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_RESET, 0xf8, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while restarting device")
        sleep(4.0);

    def setFrequency(self):
        c1 = self.frequency >> 24
        c2 = self.frequency >> 16 & 0xFF
        c3 = self.frequency >> 8 & 0xFF
        c4 = self.frequency & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_FREQUENCY])+data+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring frequency for "+str(self))

    def setBandwidth(self):
        c1 = self.bandwidth >> 24
        c2 = self.bandwidth >> 16 & 0xFF
        c3 = self.bandwidth >> 8 & 0xFF
        c4 = self.bandwidth & 0xFF
        data = KISS.escape(bytes([c1])+bytes([c2])+bytes([c3])+bytes([c4]))

        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_BANDWIDTH])+data+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring bandwidth for "+str(self))

    def setTXPower(self):
        txp = bytes([self.txpower])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_TXPOWER])+txp+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring TX power for "+str(self))

    def setSpreadingFactor(self):
        sf = bytes([self.sf])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_SF])+sf+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring spreading factor for "+str(self))

    def setCodingRate(self):
        cr = bytes([self.cr])
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_CR])+cr+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring coding rate for "+str(self))

    def setRadioState(self, state):
        self.state = state
        kiss_command = bytes([KISS.FEND])+bytes([KISS.CMD_RADIO_STATE])+bytes([state])+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring radio state for "+str(self))

    def validate_firmware(self):
        if (self.maj_version >= RNodeInterface.REQUIRED_FW_VER_MAJ):
            if (self.min_version >= RNodeInterface.REQUIRED_FW_VER_MIN):
                self.firmware_ok = True
        
        if self.firmware_ok:
            return

        RNS.log("The firmware version of the connected RNode is "+str(self.maj_version)+"."+str(self.min_version), RNS.LOG_ERROR)
        RNS.log("This version of Reticulum requires at least version "+str(RNodeInterface.REQUIRED_FW_VER_MAJ)+"."+str(RNodeInterface.REQUIRED_FW_VER_MIN), RNS.LOG_ERROR)
        RNS.log("Please update your RNode firmware with rnodeconf from https://github.com/markqvist/rnodeconfigutil/")
        error_description  = "The firmware version of the connected RNode is "+str(self.maj_version)+"."+str(self.min_version)+". "
        error_description += "This version of Reticulum requires at least version "+str(RNodeInterface.REQUIRED_FW_VER_MAJ)+"."+str(RNodeInterface.REQUIRED_FW_VER_MIN)+". "
        error_description += "Please update your RNode firmware with rnodeconf from: https://github.com/markqvist/rnodeconfigutil/"
        self.hw_errors.append({"error": KISS.ERROR_INVALID_FIRMWARE, "description": error_description})


    def validateRadioState(self):
        RNS.log("Wating for radio configuration validation for "+str(self)+"...", RNS.LOG_VERBOSE)
        if not self.platform == KISS.PLATFORM_ESP32:
            sleep(1.00);
        else:
            sleep(2.00);

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

        def af():
            self.owner.inbound(data, self)
        threading.Thread(target=af, daemon=True).start()

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

                written = self.write_mux(frame)
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

            # TODO: Ensure hotplug support for serial drivers
            # This should work now with the new time-based
            # detect polling.
            while (self.serial != None and self.serial.is_open) or (self.bt_manager != None and self.bt_manager.connected):
                serial_bytes = self.read_mux()
                got = len(serial_bytes)
                if got > 0:
                    self.last_port_io = time.time()

                for byte in serial_bytes:
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
                                RNS.log(str(self)+" Radio reporting state is online", RNS.LOG_DEBUG)
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
                            elif (byte == KISS.ERROR_INITRADIO):
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

                if got == 0:
                    time_since_last = int(time.time()*1000) - last_read_ms
                    if len(data_buffer) > 0 and time_since_last > self.timeout:
                        RNS.log(str(self)+" serial read timeout", RNS.LOG_DEBUG)
                        data_buffer = b""
                        in_frame = False
                        command = KISS.CMD_UNKNOWN
                        escape = False

                    if self.id_interval != None and self.id_callsign != None:
                        if self.first_tx != None:
                            if time.time() > self.first_tx + self.id_interval:
                                RNS.log("Interface "+str(self)+" is transmitting beacon data: "+str(self.id_callsign.decode("utf-8")), RNS.LOG_DEBUG)
                                self.processOutgoing(self.id_callsign)
                    
                    if (time.time() - self.last_port_io > self.port_io_timeout):
                        self.detect()
                    
                    if (time.time() - self.last_port_io > self.port_io_timeout*3):
                        raise IOError("Connected port for "+str(self)+" became unresponsive")

                    if self.bt_manager != None:
                        sleep(0.08)

        except Exception as e:
            self.online = False
            RNS.log("A serial port occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is now offline.", RNS.LOG_ERROR)

            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)

        self.online = False

        if self.serial != None:
            self.serial.close()

        if self.bt_manager != None:
            self.bt_manager.close()

        self.reconnect_port()

    def reconnect_port(self):
        while not self.online and len(self.hw_errors) == 0:
            try:
                time.sleep(self.reconnect_w)
                if self.serial != None and self.port != None:
                    RNS.log("Attempting to reconnect serial port "+str(self.port)+" for "+str(self)+"...", RNS.LOG_VERBOSE)

                if self.bt_manager != None:
                    RNS.log("Attempting to reconnect Bluetooth device for "+str(self)+"...", RNS.LOG_VERBOSE)

                self.open_port()

                if hasattr(self, "serial") and self.serial != None and self.serial.is_open:
                    self.configure_device()
                    if self.online:
                        if self.last_imagedata != None:
                            self.display_image(self.last_imagedata)
                            self.enable_external_framebuffer()
                
                elif hasattr(self, "bt_manager") and self.bt_manager != None and self.bt_manager.connected:
                    self.configure_device()
                    if self.online:
                        if self.last_imagedata != None:
                            self.display_image(self.last_imagedata)
                            self.enable_external_framebuffer()

            except Exception as e:
                RNS.log("Error while reconnecting RNode, the contained exception was: "+str(e), RNS.LOG_ERROR)

        if self.online:
            RNS.log("Reconnected serial port for "+str(self))

    def detach(self):
        self.disable_external_framebuffer()
        self.setRadioState(KISS.RADIO_STATE_OFF)
        self.leave()

    def __str__(self):
        return "RNodeInterface["+str(self.name)+"]"

