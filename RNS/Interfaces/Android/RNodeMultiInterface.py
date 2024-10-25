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

from RNS.Interfaces.Interface import Interface

from time import sleep
import sys
import threading
import time
import math
import RNS

try:
    from able import BluetoothDispatcher, GATT_SUCCESS
except Exception as e:
    GATT_SUCCESS = 0x00
    class BluetoothDispatcher():
        def __init__(**kwargs):
            RNS.log("Attempt to initialise BLE connectivity, but Android BLE support library is unavailable", RNS.LOG_ERROR)
            raise OSError("No BLE support available")

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
    CMD_INTERFACES  = 0x64

    CMD_INT0_DATA   = 0x00
    CMD_INT1_DATA   = 0x10
    CMD_INT2_DATA   = 0x20
    CMD_INT3_DATA   = 0x70
    CMD_INT4_DATA   = 0x80
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
    CMD_SEL_INT3    = 0x7F
    CMD_SEL_INT4    = 0x8F
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


class AndroidBluetoothManager():
    DEVICE_TYPE_CLASSIC = 1
    DEVICE_TYPE_LE = 2
    DEVICE_TYPE_DUAL = 3

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
            RNS.log("Could not query paired devices, Bluetooth is disabled", RNS.LOG_EXTREME)
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
                    RNS.log("Could not create and connect Bluetooth RFcomm socket for "+str(device.getName())+" "+str(device.getAddress()), RNS.LOG_EXTREME)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_EXTREME)

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

class RNodeMultiInterface(Interface):
    MAX_CHUNK = 32768

    CALLSIGN_MAX_LEN    = 32

    REQUIRED_FW_VER_MAJ = 1
    REQUIRED_FW_VER_MIN = 73

    RECONNECT_WAIT = 5

    PORT_IO_TIMEOUT = 3

    MAX_SUBINTERFACES = 11

    BATTERY_STATE_UNKNOWN     = 0x00
    BATTERY_STATE_DISCHARGING = 0x01
    BATTERY_STATE_CHARGING    = 0x02
    BATTERY_STATE_CHARGED     = 0x03

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
        self, owner, name, port, subint_config, flow_control = False, id_interval = None,
        allow_bluetooth = False, target_device_name = None,
        target_device_address = None, id_callsign = None, st_alock = None, lt_alock = None,
        ble_addr = None, ble_name = None, force_ble = False):
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
        self.hw_errors   = []
        self.allow_bluetooth = allow_bluetooth

        self.use_ble     = False
        self.ble_name    = ble_name
        self.ble_addr    = ble_addr
        self.ble         = None
        self.ble_rx_lock = threading.Lock()
        self.ble_tx_lock = threading.Lock()
        self.ble_rx_queue= b""
        self.ble_tx_queue= b""

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
        self.reconnect_lock = threading.Lock()

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

        self.r_battery_state = RNodeMultiInterface.BATTERY_STATE_UNKNOWN
        self.r_battery_percent = 0

        self.packet_queue    = []
        self.interface_ready = False
        self.announce_rate_target = None
        self.last_port_io = 0
        self.port_io_timeout = RNodeMultiInterface.PORT_IO_TIMEOUT
        self.last_imagedata = None

        if force_ble or self.ble_addr != None or self.ble_name != None:
            self.use_ble = True

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
        if not self.use_ble:
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
                        ble_dispatcher = self.ble,
                        target_device_name = self.bt_target_device_name,
                        target_device_address = self.bt_target_device_address
                    )

                if self.bt_manager != None:
                    self.bt_manager.connect_any_device()
        else:
            if self.ble == None:
                self.ble = BLEConnection(owner=self, target_name=self.ble_name, target_bt_addr=self.ble_addr)
                self.serial = self.ble

            open_time = time.time()
            while not self.ble.connected and time.time() < open_time + self.ble.CONNECT_TIMEOUT:
                time.sleep(1)

    def resetRadioState(self):
        self.r_frequency = None
        self.r_bandwidth = None
        self.r_txpower = None
        self.r_sf = None
        self.r_cr = None
        self.r_state = None

    def configure_device(self):
        self.resetRadioState()
        sleep(2.0)
        thread = threading.Thread(target=self.readLoop, daemon=True).start()

        self.detect()
        if not self.use_ble:
            sleep(0.5)
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
            raise IOError("Could not detect device")
        else:
            if self.platform == KISS.PLATFORM_ESP32 or self.platform == KISS.PLATFORM_NRF52:
                self.display = True

        if not self.firmware_ok:
            raise IOError("Invalid device firmware")

        if self.serial != None and self.port != None:
            self.timeout = 200
            RNS.log("Serial port "+self.port+" is now open")

        if self.bt_manager != None and self.bt_manager.connected:
            self.timeout = 1500
            RNS.log("Bluetooth connection to RNode now open")

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

                if not interface.online:
                    self.online = False
                    raise IOError(str(interface) + " failed to initialise.")

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
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while detecting hardware for "+str(self))
    
    def leave(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_LEAVE, 0xFF, KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while sending host left command to device")
    
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
            
            written = self.write_mux(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while writing framebuffer data device")

    def hard_reset(self):
        kiss_command = bytes([KISS.FEND, KISS.CMD_RESET, 0xf8, KISS.FEND])
        written = self.write_mux(kiss_command)
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
        written = self.write_mux(kiss_command)
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
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring bandwidth for "+str(self))
        self.selected_index = interface.index

    def setTXPower(self, txpower, interface):
        txp = txpower.to_bytes(1, byteorder="big", signed=True)
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_TXPOWER])+txp+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring TX power for "+str(self))
        self.selected_index = interface.index

    def setSpreadingFactor(self, sf, interface):
        sf = bytes([sf])
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_SF])+sf+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
        if written != len(kiss_command):
            raise IOError("An IO error occurred while configuring spreading factor for "+str(self))
        self.selected_index = interface.index

    def setCodingRate(self, cr, interface):
        cr = bytes([cr])
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_CR])+cr+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
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
            written = self.write_mux(kiss_command)
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
            written = self.write_mux(kiss_command)
            if written != len(kiss_command):
                raise IOError("An IO error occurred while configuring long-term airtime limit for "+str(self))
            self.selected_index = interface.index

    def setRadioState(self, state, interface):
        #self.state = state
        kiss_command = bytes([KISS.FEND])+bytes([interface.sel_cmd])+bytes([KISS.FEND])+bytes([KISS.FEND])+bytes([KISS.CMD_RADIO_STATE])+bytes([state])+bytes([KISS.FEND])
        written = self.write_mux(kiss_command)
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
        error_description  = "The firmware version of the connected RNode is "+str(self.maj_version)+"."+str(self.min_version)+". "
        error_description += "This version of Reticulum requires at least version "+str(RNodeMultiInterface.REQUIRED_FW_VER_MAJ)+"."+str(RNodeMultiInterface.REQUIRED_FW_VER_MIN)+". "
        error_description += "Please update your RNode firmware with rnodeconf from: https://github.com/markqvist/Reticulum/RNS/Utilities/rnodeconf.py"
        self.hw_errors.append({"error": KISS.ERROR_INVALID_FIRMWARE, "description": error_description})

    def processOutgoing(self, data, interface = None):
        if interface is None:
            # do nothing if RNS tries to transmit on this interface directly
            pass
        else:
            data    = KISS.escape(data)
            frame   = bytes([0xc0])+bytes([interface.data_cmd])+data+bytes([0xc0])

            written = self.write_mux(frame)
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

            while (self.serial != None and self.serial.is_open) or (self.bt_manager != None and self.bt_manager.connected):
                serial_bytes = self.read_mux()
                got = len(serial_bytes)
                if got > 0:
                    self.last_port_io = time.time()

                for byte in serial_bytes:
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
                                    if self.subinterfaces[self.selected_index] is not int:
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
                                    if self.subinterfaces[self.selected_index] is not int:
                                        self.subinterfaces[self.selected_index].r_bandwidth = command_buffer[0] << 24 | command_buffer[1] << 16 | command_buffer[2] << 8 | command_buffer[3]
                                        RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting bandwidth is "+str(self.subinterfaces[self.selected_index].r_bandwidth/1000.0)+" KHz", RNS.LOG_DEBUG)
                                        self.subinterfaces[self.selected_index].updateBitrate()

                        elif (command == KISS.CMD_TXPOWER):
                            txp = byte - 256 if byte > 127 else byte
                            if self.subinterfaces[self.selected_index] is not int:
                                self.subinterfaces[self.selected_index].r_txpower = txp
                                RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting TX power is "+str(self.subinterfaces[self.selected_index].r_txpower)+" dBm", RNS.LOG_DEBUG)
                        elif (command == KISS.CMD_SF):
                            if self.subinterfaces[self.selected_index] is not int:
                                self.subinterfaces[self.selected_index].r_sf = byte
                                RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting spreading factor is "+str(self.subinterfaces[self.selected_index].r_sf), RNS.LOG_DEBUG)
                                self.subinterfaces[self.selected_index].updateBitrate()
                        elif (command == KISS.CMD_CR):
                            if self.subinterfaces[self.selected_index] is not int:
                                self.subinterfaces[self.selected_index].r_cr = byte
                                RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting coding rate is "+str(self.subinterfaces[self.selected_index].r_cr), RNS.LOG_DEBUG)
                                self.subinterfaces[self.selected_index].updateBitrate()
                        elif (command == KISS.CMD_RADIO_STATE):
                            if self.subinterfaces[self.selected_index] is not int:
                                self.subinterfaces[self.selected_index].r_state = byte
                                if self.subinterfaces[self.selected_index].r_state:
                                    RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting state is online", RNS.LOG_DEBUG)
                                else:
                                    RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting state is offline", RNS.LOG_DEBUG)

                        elif (command == KISS.CMD_RADIO_LOCK):
                            if self.subinterfaces[self.selected_index] is not int:
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
                            if self.subinterfaces[self.selected_index] is not int:
                                self.subinterfaces[self.selected_index].r_stat_rssi = byte-RNodeSubInterface.RSSI_OFFSET
                        elif (command == KISS.CMD_STAT_SNR):
                            if self.subinterfaces[self.selected_index] is not int:
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
                                    if self.subinterfaces[self.selected_index] is not int:
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
                                    if self.subinterfaces[self.selected_index] is not int:
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

                                    if self.subinterfaces[self.selected_index] is not int:
                                        if lst != self.subinterfaces[self.selected_index].r_symbol_time_ms or lsr != self.subinterfaces[self.selected_index].r_symbol_rate or prs != self.subinterfaces[self.selected_index].r_preamble_symbols or prt != self.subinterfaces[self.selected_index].r_premable_time_ms or cst != self.subinterfaces[self.selected_index].r_csma_slot_time_ms:
                                            self.subinterfaces[self.selected_index].r_symbol_time_ms    = lst
                                            self.subinterfaces[self.selected_index].r_symbol_rate       = lsr
                                            self.subinterfaces[self.selected_index].r_preamble_symbols  = prs
                                            self.subinterfaces[self.selected_index].r_premable_time_ms  = prt
                                            self.subinterfaces[self.selected_index].r_csma_slot_time_ms = cst
                                            RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting symbol time is "+str(round(self.subinterfaces[self.selected_index].r_symbol_time_ms,2))+"ms (at "+str(self.subinterfaces[self.selected_index].r_symbol_rate)+" baud)", RNS.LOG_DEBUG)
                                            RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting preamble is "+str(self.subinterfaces[self.selected_index].r_preamble_symbols)+" symbols ("+str(self.subinterfaces[self.selected_index].r_premable_time_ms)+"ms)", RNS.LOG_DEBUG)
                                            RNS.log(str(self.subinterfaces[self.selected_index])+" Radio reporting CSMA slot time is "+str(self.subinterfaces[self.selected_index].r_csma_slot_time_ms)+"ms", RNS.LOG_DEBUG)
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
                        
                if got == 0:
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
                    
                    if (time.time() - self.last_port_io > self.port_io_timeout):
                        self.detect()
                    
                    if (time.time() - self.last_port_io > self.port_io_timeout*3):
                        raise IOError("Connected port for "+str(self)+" became unresponsive")

                    if self.bt_manager != None:
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

        if self.serial != None:
            self.serial.close()

        if self.bt_manager != None:
            self.bt_manager.close()

        if not self.detached and not self.reconnecting:
            self.reconnect_port()

    def reconnect_port(self):
        if self.reconnect_lock.locked():
            RNS.log("Dropping superflous reconnect port job")
            return

        while not self.online and len(self.hw_errors) == 0:
            try:
                time.sleep(self.reconnect_w)
                if self.serial != None and self.port != None:
                    RNS.log("Attempting to reconnect serial port "+str(self.port)+" for "+str(self)+"...", RNS.LOG_EXTREME)

                if self.bt_manager != None:
                    RNS.log("Attempting to reconnect Bluetooth device for "+str(self)+"...", RNS.LOG_EXTREME)

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
        self.detached = True
        self.disable_external_framebuffer()

        for interface in self.subinterfaces:
            if interface != 0:
                self.setRadioState(KISS.RADIO_STATE_OFF, interface)
        self.leave()

        if self.use_ble:
            self.ble.close()

    def teardown_subinterfaces(self):
        for interface in self.subinterfaces:
            if interface != 0:
                if interface in RNS.Transport.interfaces:
                    RNS.Transport.interfaces.remove(interface)
                self.subinterfaces[interface.index] = 0

    def should_ingress_limit(self):
        return False

    def get_battery_state(self):
        return self.r_battery_state

    def get_battery_state_string(self):
        if self.r_battery_state == RNodeMultiInterface.BATTERY_STATE_CHARGED:
            return "charged"
        elif  self.r_battery_state == RNodeMultiInterface.BATTERY_STATE_CHARGING:
            return "charging"
        elif self.r_battery_state == RNodeMultiInterface.BATTERY_STATE_DISCHARGING:
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
        if not RNS.vendor.platformutils.is_android():
            raise SystemError("Android-specific interface was used on non-Android OS")

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
        time.sleep(0.15)
        self.parent_interface.setBandwidth(self.bandwidth, self)
        time.sleep(0.15)
        self.parent_interface.setTXPower(self.txpower, self)
        time.sleep(0.15)
        self.parent_interface.setSpreadingFactor(self.sf, self)
        time.sleep(0.15)
        self.parent_interface.setCodingRate(self.cr, self)
        time.sleep(0.15)
        self.parent_interface.setSTALock(self.st_alock, self)
        time.sleep(0.15)
        self.parent_interface.setLTALock(self.lt_alock, self)
        time.sleep(0.15)
        self.parent_interface.setRadioState(KISS.RADIO_STATE_ON, self)
        time.sleep(0.15)
        self.state = KISS.RADIO_STATE_ON

        if self.parent_interface.use_ble:
            time.sleep(1)

    def validateRadioState(self):
        RNS.log("Waiting for radio configuration validation for "+str(self)+"...", RNS.LOG_VERBOSE)
        if not self.platform == KISS.PLATFORM_ESP32:
            sleep(1.00)
        else:
            sleep(2.00)

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

class BLEConnection(BluetoothDispatcher):
    UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    MAX_GATT_ATTR_LEN = 512
    BASE_MTU          = 20
    TARGET_MTU        = 512

    MTU_TIMEOUT = 4.0
    CONNECT_TIMEOUT = 7.0
    RECONNECT_WAIT = 1.0

    @property
    def is_open(self):
        return self.connected

    @property
    def in_waiting(self):
        return len(self.owner.ble_rx_queue) > 0

    def write(self, data_bytes):
        with self.owner.ble_tx_lock:
            self.owner.ble_tx_queue += data_bytes
            return len(data_bytes)

    def read(self):
        with self.owner.ble_rx_lock:
            data = self.owner.ble_rx_queue
            self.owner.ble_rx_queue = b""
            return data

    def close(self):
        try:
            if self.connected:
                RNS.log(f"Disconnecting BLE device from {self.owner}", RNS.LOG_DEBUG)
                # RNS.log("Waiting for BLE write buffer to empty...")
                timeout = time.time() + 10
                while self.owner.ble_waiting() and self.write_thread != None and time.time() < timeout:
                    time.sleep(0.1)
                # if time.time() > timeout:
                #     RNS.log("Writing timed out")
                # else:
                #     RNS.log("Writing concluded")

                self.rx_char = None
                self.tx_char = None
                self.mtu = BLEConnection.BASE_MTU
                self.mtu_requested_time = None

                if self.write_thread != None:
                    # RNS.log("Waiting for write thread to finish...")
                    while self.write_thread != None:
                        time.sleep(0.1)

                # RNS.log("Writing finished, closing GATT connection")
                self.close_gatt()

                with self.owner.ble_rx_lock:
                    self.owner.ble_rx_queue = b""

                with self.owner.ble_tx_lock:
                    self.owner.ble_tx_queue = b""

                self.connected = False
                self.ble_device = None

        except Exception as e:
            RNS.log("An error occurred while closing BLE connection for {self.owner}: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    def __init__(self, owner=None, target_name=None, target_bt_addr=None):
        super(BLEConnection, self).__init__()
        self.owner = owner
        self.target_name = target_name
        self.target_bt_addr = target_bt_addr
        self.connect_timeout = BLEConnection.CONNECT_TIMEOUT
        self.ble_device = None
        self.rx_char = None
        self.tx_char = None
        self.connected = False
        self.was_connected = False
        self.connected_time = None
        self.mtu_requested_time = None
        self.running = False
        self.should_run = False
        self.connect_job_running = False
        self.write_thread = None
        self.mtu = BLEConnection.BASE_MTU
        self.target_mtu = BLEConnection.TARGET_MTU

        self.bt_manager = AndroidBluetoothManager(owner=self)

        self.should_run = True
        self.connection_thread = threading.Thread(target=self.connection_job, daemon=True).start()

    def write_loop(self):
        try:
            while self.connected and self.rx_char != None:
                if self.owner.ble_waiting():
                    data = self.owner.get_ble_waiting(self.mtu)
                    self.write_characteristic(self.rx_char, data)
                else:
                    time.sleep(0.1)
        
        except Exception as e:
            RNS.log("An error occurred in {self} write loop: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

        self.write_thread = None

    def connection_job(self):
        while self.should_run:
            if self.bt_manager.bt_enabled():
                if self.ble_device == None:
                    self.ble_device = self.find_target_device()

                if self.ble_device != None:
                    if not self.connected:
                        if self.was_connected:
                            RNS.log(f"Throttling BLE reconnect for {BLEConnection.RECONNECT_WAIT} seconds", RNS.LOG_DEBUG)
                            time.sleep(BLEConnection.RECONNECT_WAIT)

                        self.connect_device()

            else:
                if self.connected:
                    RNS.log("Bluetooth was disabled, closing active BLE device connection", RNS.LOG_ERROR)
                    self.close()

            time.sleep(2)

    def connect_device(self):
        if self.ble_device != None and self.bt_manager.bt_enabled():
            RNS.log(f"Trying to connect BLE device {self.ble_device.getName()} / {self.ble_device.getAddress()} for {self.owner}...", RNS.LOG_DEBUG)
            self.mtu = BLEConnection.BASE_MTU
            self.connect_by_device_address(self.ble_device.getAddress())
            end = time.time() + BLEConnection.CONNECT_TIMEOUT
            while time.time() < end and not self.connected:
                time.sleep(0.25)

            if self.connected:
                self.owner.port = f"ble://{self.ble_device.getAddress()}"
                self.write_thread = threading.Thread(target=self.write_loop, daemon=True)
                self.write_thread.start()
            else:
                RNS.log(f"BLE device connection timed out for {self.owner}", RNS.LOG_DEBUG)
                if self.mtu_requested_time:
                    RNS.log("MTU update timeout, tearing down connection")
                    self.owner.hw_errors.append({"error": KISS.ERROR_INVALID_BLE_MTU, "description": "The Bluetooth Low Energy transfer MTU could not be configured for the connected device, and communication has failed. Restart Reticulum and any connected applications to retry connecting."})
                    self.close()
                    self.should_run = False
                
                self.close_gatt()

            self.connect_job_running = False

    def device_disconnected(self):
        RNS.log(f"BLE device for {self.owner} disconnected", RNS.LOG_NOTICE)
        self.connected = False
        self.ble_device = None
        self.close_gatt()

    def find_target_device(self):
        found_device = None
        potential_devices = self.bt_manager.get_paired_devices()

        if self.target_bt_addr != None:
            for device in potential_devices:
                if (device.getType() == AndroidBluetoothManager.DEVICE_TYPE_LE) or (device.getType() == AndroidBluetoothManager.DEVICE_TYPE_DUAL):
                    if str(device.getAddress()).replace(":", "").lower() == str(self.target_bt_addr).replace(":", "").lower():
                        found_device = device
                        break

        if not found_device and self.target_name != None:
            for device in potential_devices:
                if (device.getType() == AndroidBluetoothManager.DEVICE_TYPE_LE) or (device.getType() == AndroidBluetoothManager.DEVICE_TYPE_DUAL):
                    if device.getName().lower() == self.target_name.lower():
                        found_device = device
                        break

        if not found_device:
            for device in potential_devices:
                if (device.getType() == AndroidBluetoothManager.DEVICE_TYPE_LE) or (device.getType() == AndroidBluetoothManager.DEVICE_TYPE_DUAL):
                    if device.getName().startswith("RNode "):
                        found_device = device
                        break

        return found_device

    def on_connection_state_change(self, status, state):
        if status == GATT_SUCCESS and state:
            self.discover_services()
        else:
            self.device_disconnected()

    def on_services(self, status, services):
        if status == GATT_SUCCESS:
            self.rx_char = services.search(BLEConnection.UART_RX_CHAR_UUID)
            
            if self.rx_char is not None:
                self.tx_char = services.search(BLEConnection.UART_TX_CHAR_UUID)

                if self.tx_char is not None:                
                    if self.enable_notifications(self.tx_char):
                        RNS.log("Enabled notifications for BLE TX characteristic", RNS.LOG_DEBUG)
                        
                        RNS.log(f"Requesting BLE connection MTU update to {self.target_mtu}", RNS.LOG_DEBUG)
                        self.mtu_requested_time = time.time()
                        self.request_mtu(self.target_mtu)

                    else:
                        RNS.log("Could not enable notifications for BLE TX characteristic", RNS.LOG_ERROR)

        else:
            RNS.log("BLE device service discovery failure", RNS.LOG_ERROR)

    def on_mtu_changed(self, mtu, status):
        if status == GATT_SUCCESS:
            self.mtu = min(mtu-5, BLEConnection.MAX_GATT_ATTR_LEN)
            RNS.log(f"BLE MTU updated to {self.mtu} for {self.owner}", RNS.LOG_DEBUG)
            self.connected = True
            self.was_connected = True
            self.connected_time = time.time()
            self.mtu_requested_time = None

        else:
            RNS.log(f"MTU update request did not succeed, mtu={mtu}, status={status}", RNS.LOG_ERROR)

    def on_characteristic_changed(self, characteristic):
        if characteristic.getUuid().toString() == BLEConnection.UART_TX_CHAR_UUID:
            recvd = bytes(characteristic.getValue())
            self.owner.ble_receive(recvd)
