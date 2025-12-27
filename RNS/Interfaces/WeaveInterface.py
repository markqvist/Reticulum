# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import RNS
import threading
import time

from collections import deque
from RNS.Interfaces.Interface import Interface

class HDLC():
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

class WDCL():
    WDCL_T_DISCOVER        = 0x00
    WDCL_T_CONNECT         = 0x01
    WDCL_T_CMD             = 0x02
    WDCL_T_LOG             = 0x03
    WDCL_T_DISP            = 0x04
    WDCL_T_ENDPOINT_PKT    = 0x05
    WDCL_T_ENCAP_PROTO     = 0x06

    WDCL_BROADCAST         = bytes([0xFF, 0xFF, 0xFF, 0xFF])

    WDCL_HANDSHAKE_TIMEOUT = 2

    HEADER_MINSIZE         = 4+1
    MAX_CHUNK              = 32768
    port                   = None
    speed                  = None
    databits               = None
    parity                 = None
    stopbits               = None
    serial                 = None

    def __init__(self, owner, device, port, as_interface=False):
        import importlib.util
        if RNS.vendor.platformutils.is_android():
            self.on_android  = True
            if importlib.util.find_spec('usbserial4a') != None:
                from usbserial4a import serial4a as serial
                parity = "N"

                if importlib.util.find_spec('jnius') == None:
                    RNS.log("Could not load jnius API wrapper for Android, RNode interface cannot be created.", RNS.LOG_CRITICAL)
                    RNS.log("This probably means you are trying to use an USB-based interface from within Termux or similar.", RNS.LOG_CRITICAL)
                    RNS.log("This is currently not possible, due to this environment limiting access to the native Android APIs.", RNS.LOG_CRITICAL)
                    RNS.panic()

            else:
                RNS.log("Could not load USB serial module for Android, Weave interface cannot be created.", RNS.LOG_CRITICAL)
                RNS.panic()
        
        else:
            self.on_android = False
            if importlib.util.find_spec('serial') != None:
                import serial
                parity = serial.PARITY_NONE
            else:
                RNS.log("Using the Weave interface requires a serial communication module to be installed.", RNS.LOG_CRITICAL)
                RNS.log("You can install one with the command: python3 -m pip install pyserial", RNS.LOG_CRITICAL)
                RNS.panic()

        if not RNS.vendor.platformutils.is_android():
            if port == None: raise ValueError("No port specified")
        
        self.switch_identity = owner.switch_identity
        self.switch_id = self.switch_identity.sig_pub_bytes[-4:]
        self.switch_pub_bytes = self.switch_identity.sig_pub_bytes

        self.rxb = 0
        self.txb = 0
        self.owner = owner
        self.as_interface = as_interface
        self.device = device
        self.device.connection = self
        self.pyserial = serial
        self.serial   = None
        self.port     = port
        self.speed    = 3000000
        self.databits = 8
        self.parity   = parity
        self.stopbits = 1
        self.timeout  = 100
        self.online   = False
        self.frame_buffer = b""
        self.next_tx = 0
        self.should_run = True
        self.receiver = None
        self.wdcl_connected = False
        self.reconnecting = False
        self.frame_queue = deque()
        if not self.as_interface:
            self.id = RNS.Identity.full_hash(port.hwid.encode("utf-8"))

        if self.as_interface:
            try:
                self.open_port()
                if self.serial and self.serial.is_open: self.configure_device()
                else: raise IOError("Could not open serial port")

            except Exception as e:
                RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                RNS.log("Reticulum will attempt to bring up this interface periodically", RNS.LOG_ERROR)
                if not self.owner.detached and not self.reconnecting:
                    thread = threading.Thread(target=self.reconnect_port)
                    thread.daemon = True
                    thread.start()

        else:
            try: self.open_port()
            except Exception as e:
                self.owner.wlog("Could not open serial port")
                raise e

            if self.serial.is_open: self.configure_device()
            else: raise IOError("Could not open serial port")


    def open_port(self):
        if not self.on_android:
            if self.as_interface:
                RNS.log(f"Opening serial port {self.port}...", RNS.LOG_VERBOSE)
                target_port = self.port
            else:
                self.owner.wlog(f"Opening serial port {self.port.device}...")
                target_port = self.port.device

            self.serial = self.pyserial.Serial(
                port = target_port,
                baudrate = self.speed,
                bytesize = self.databits,
                parity = self.parity,
                stopbits = self.stopbits,
                xonxoff = False,
                rtscts = False,
                timeout = 0.250,
                inter_byte_timeout = None,
                write_timeout = None,
                dsrdtr = False)

        else:
            if self.port != None:
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

    def close(self):
        self.should_run = False
        self.online = False
        self.wdcl_connected = False
        if self.serial:
            self.serial.close()
            if self.as_interface: RNS.log((f"Closed serial port {str(self.port)} for {str(self)}"), RNS.LOG_VERBOSE) 
            else: self.owner.wlog(f"Closed serial port {str(self.port.device)} for {str(self)}")

    def configure_device(self):
        thread = threading.Thread(target=self.read_loop)
        thread.daemon = True
        thread.start()
        if self.as_interface: RNS.log(f"Serial port {self.port} is now open, discovering remote device...", RNS.LOG_VERBOSE)
        else: self.owner.wlog("Serial port "+self.port.device+" is now open")
        self.device.discover()

        if self.as_interface:
            timeout = time.time() + self.WDCL_HANDSHAKE_TIMEOUT
            while time.time() < timeout and not self.wdcl_connected: time.sleep(0.1)
            if not self.wdcl_connected:
                raise IOError(f"WDCL connection handshake timed out for {self}")
                self.online = False
                self.wdcl_connected = False
                if self.serial:
                    try: self.serial.close()
                    except Exception as e: RNS.log("Error while cleaning serial connection: {e}", RNS.LOG_ERROR)

        self.online = True

    def process_incoming(self, data):
        self.rxb += len(data)
        if self.device:
            while len(self.frame_queue): self.device.incoming_frame(self.frame_queue.pop())
            self.device.incoming_frame(data)
        else: self.frame_queue.append(data)

    def process_outgoing(self, data):
        if self.serial.is_open:
            data = bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])
            written = self.serial.write(data)
            self.txb += len(data)          
            if written != len(data):
                raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))

    def read_loop(self):
        try:
            while self.serial.is_open:
                data_in = self.serial.read(1500)
                if len(data_in) > 0:
                    self.frame_buffer += data_in
                    flags_remaining = True
                    while flags_remaining:
                        frame_start = self.frame_buffer.find(HDLC.FLAG)
                        if frame_start != -1:
                            frame_end = self.frame_buffer.find(HDLC.FLAG, frame_start+1)
                            if frame_end != -1:
                                frame = self.frame_buffer[frame_start+1:frame_end]
                                frame = frame.replace(bytes([HDLC.ESC, HDLC.FLAG ^ HDLC.ESC_MASK]), bytes([HDLC.FLAG]))
                                frame = frame.replace(bytes([HDLC.ESC, HDLC.ESC  ^ HDLC.ESC_MASK]), bytes([HDLC.ESC]))
                                if len(frame) > WDCL.HEADER_MINSIZE: self.process_incoming(frame)
                                self.frame_buffer = self.frame_buffer[frame_end:]
                            else:
                                flags_remaining = False
                        else:
                            flags_remaining = False
                    
        except Exception as e:
            self.online = False
            self.wdcl_connected = False
            if self.should_run:
                if self.as_interface:
                    RNS.log("A serial port error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
                    RNS.log("Will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)
                else:
                    self.owner.wlog("A serial port error occurred, the contained exception was: "+str(e))
                    self.owner.wlog("Will attempt to reconnect the interface periodically.")
                RNS.trace_exception(e)

        self.online = False
        self.wdcl_connected = False
        try: self.serial.close()
        except: pass
        if self.should_run: self.reconnect_port()

    def reconnect_port(self):
        if self.reconnecting: return
        self.reconnecting = True
        self.wdcl_connected = False
        while not self.online:
            try:
                time.sleep(5)
                if self.as_interface: RNS.log("Attempting to reconnect serial port "+str(self.port)+" for "+str(self.owner)+"...", RNS.LOG_DEBUG)
                else: self.owner.wlog("Attempting to reconnect serial port "+str(self.port.device)+" for "+str(self.owner)+"...")
                self.open_port()
                if self.serial and self.serial.is_open: self.configure_device()
            except Exception as e:
                if self.as_interface: RNS.log("Error while reconnecting port, the contained exception was: "+str(e), RNS.LOG_ERROR)
                else: self.owner.wlog("Error while reconnecting port, the contained exception was: "+str(e))
                RNS.trace_exception(e)

        self.reconnecting = False
        if self.as_interface: RNS.log("Reconnected serial port for "+str(self), RNS.LOG_INFO)
        else: self.owner.wlog("Reconnected serial port for "+str(self))

    def __str__(self):
        if self.as_interface: return f"WDCL over {self.port}"
        else:
            if self.port.serial_number: sn_str = f" {self.port.serial_number}"
            else: sn_str = ""
            return f"{self.port.product}{sn_str} (USB)"

class Cmd():
    WDCL_CMD_ENDPOINT_PKT        = 0x0001
    WDCL_CMD_ENDPOINTS_LIST      = 0x0100
    WDCL_CMD_REMOTE_DISPLAY      = 0x0A00
    WDCL_CMD_REMOTE_INPUT        = 0x0A01

class Evt():
    ET_MSG                       = 0x0000
    ET_SYSTEM_BOOT               = 0x0001
    ET_CORE_INIT                 = 0x0002
    ET_DRV_UART_INIT             = 0x1000
    ET_DRV_USB_CDC_INIT          = 0x1010
    ET_DRV_USB_CDC_HOST_AVAIL    = 0x1011
    ET_DRV_USB_CDC_HOST_SUSPEND  = 0x1012
    ET_DRV_USB_CDC_HOST_RESUME   = 0x1013
    ET_DRV_USB_CDC_CONNECTED     = 0x1014
    ET_DRV_USB_CDC_READ_ERR      = 0x1015
    ET_DRV_USB_CDC_OVERFLOW      = 0x1016
    ET_DRV_USB_CDC_DROPPED       = 0x1017
    ET_DRV_USB_CDC_TX_TIMEOUT    = 0x1018
    ET_DRV_I2C_INIT              = 0x1020
    ET_DRV_NVS_INIT              = 0x1030
    ET_DRV_NVS_ERASE             = 0x1031
    ET_DRV_CRYPTO_INIT           = 0x1040
    ET_DRV_DISPLAY_INIT          = 0x1050
    ET_DRV_DISPLAY_BUS_AVAILABLE = 0x1051
    ET_DRV_DISPLAY_IO_CONFIGURED = 0x1052
    ET_DRV_DISPLAY_PANEL_CREATED = 0x1053
    ET_DRV_DISPLAY_PANEL_RESET   = 0x1054
    ET_DRV_DISPLAY_PANEL_INIT    = 0x1055
    ET_DRV_DISPLAY_PANEL_ENABLE  = 0x1056
    ET_DRV_DISPLAY_REMOTE_ENABLE = 0x1057
    ET_DRV_W80211_INIT           = 0x1060
    ET_DRV_W80211_INIT           = 0x1061
    ET_DRV_W80211_CHANNEL        = 0x1062
    ET_DRV_W80211_POWER          = 0x1063
    ET_KRN_LOGGER_INIT           = 0x2000
    ET_KRN_LOGGER_OUTPUT         = 0x2001
    ET_KRN_UI_INIT               = 0x2010
    ET_PROTO_WDCL_INIT           = 0x3000
    ET_PROTO_WDCL_RUNNING        = 0x3001
    ET_PROTO_WDCL_CONNECTION     = 0x3002
    ET_PROTO_WDCL_HOST_ENDPOINT  = 0x3003
    ET_PROTO_WEAVE_INIT          = 0x3100
    ET_PROTO_WEAVE_RUNNING       = 0x3101
    ET_PROTO_WEAVE_EP_ALIVE      = 0x3102
    ET_PROTO_WEAVE_EP_TIMEOUT    = 0x3103
    ET_PROTO_WEAVE_EP_VIA        = 0x3104
    ET_SRVCTL_REMOTE_DISPLAY     = 0xA000
    ET_INTERFACE_REGISTERED      = 0xD000
    ET_STAT_STATE                = 0xE000
    ET_STAT_UPTIME               = 0xE001
    ET_STAT_TIMEBASE             = 0xE002
    ET_STAT_CPU                  = 0xE003
    ET_STAT_TASK_CPU             = 0xE004
    ET_STAT_MEMORY               = 0xE005
    ET_STAT_STORAGE              = 0xE006
    ET_SYSERR_MEM_EXHAUSTED      = 0xF000

    IF_TYPE_USB                  = 0x01
    IF_TYPE_UART                 = 0x02
    IF_TYPE_W80211               = 0x03
    IF_TYPE_BLE                  = 0x04
    IF_TYPE_LORA                 = 0x05
    IF_TYPE_ETHERNET             = 0x06
    IF_TYPE_WIFI                 = 0x07
    IF_TYPE_TCP                  = 0x08
    IF_TYPE_UDP                  = 0x09
    IF_TYPE_IR                   = 0x0A
    IF_TYPE_AFSK                 = 0x0B
    IF_TYPE_GPIO                 = 0x0C
    IF_TYPE_SPI                  = 0x0D
    IF_TYPE_I2C                  = 0x0E
    IF_TYPE_CAN                  = 0x0F
    IF_TYPE_DMA                  = 0x10

    event_descriptions = {
        ET_SYSTEM_BOOT: "System boot",
        ET_CORE_INIT: "Core initialization",
        ET_DRV_UART_INIT: "UART driver initialization",
        ET_DRV_USB_CDC_INIT: "USB CDC driver initialization",
        ET_DRV_USB_CDC_HOST_AVAIL: "USB CDC host became available",
        ET_DRV_USB_CDC_HOST_SUSPEND: "USB CDC host suspend",
        ET_DRV_USB_CDC_HOST_RESUME: "USB CDC host resume",
        ET_DRV_USB_CDC_CONNECTED: "USB CDC host connection",
        ET_DRV_USB_CDC_READ_ERR: "USB CDC read error",
        ET_DRV_USB_CDC_OVERFLOW: "USB CDC overflow occurred",
        ET_DRV_USB_CDC_DROPPED: "USB CDC dropped bytes",
        ET_DRV_USB_CDC_TX_TIMEOUT: "USB CDC TX flush timeout",
        ET_DRV_I2C_INIT: "I2C driver initialization",
        ET_DRV_NVS_INIT: "NVS driver initialization",
        ET_DRV_CRYPTO_INIT: "Cryptography driver initialization",
        ET_DRV_W80211_INIT: "W802.11 driver initialization",
        ET_DRV_W80211_CHANNEL: "W802.11 channel configuration",
        ET_DRV_W80211_POWER: "W802.11 TX power configuration",
        ET_DRV_DISPLAY_INIT: "Display driver initialization",
        ET_DRV_DISPLAY_BUS_AVAILABLE: "Display bus availability",
        ET_DRV_DISPLAY_IO_CONFIGURED: "Display I/O configuration",
        ET_DRV_DISPLAY_PANEL_CREATED: "Display panel allocation",
        ET_DRV_DISPLAY_PANEL_RESET: "Display panel reset",
        ET_DRV_DISPLAY_PANEL_INIT: "Display panel initialization",
        ET_DRV_DISPLAY_PANEL_ENABLE: "Display panel activation",
        ET_DRV_DISPLAY_REMOTE_ENABLE: "Remote display output activation",
        ET_KRN_LOGGER_INIT: "Logging service initialization",
        ET_KRN_LOGGER_OUTPUT: "Logging service output activation",
        ET_KRN_UI_INIT: "User interface service initialization",
        ET_PROTO_WDCL_INIT: "WDCL protocol initialization",
        ET_PROTO_WDCL_RUNNING: "WDCL protocol activation",
        ET_PROTO_WDCL_CONNECTION: "WDCL host connection",
        ET_PROTO_WDCL_HOST_ENDPOINT: "Weave host endpoint",
        ET_PROTO_WEAVE_INIT: "Weave protocol initialization",
        ET_PROTO_WEAVE_RUNNING: "Weave protocol activation",
        ET_PROTO_WEAVE_EP_ALIVE: "Weave endpoint alive",
        ET_PROTO_WEAVE_EP_TIMEOUT: "Weave endpoint disappeared",
        ET_SRVCTL_REMOTE_DISPLAY: "Remote display service control event",
        ET_INTERFACE_REGISTERED: "Interface registration",
        ET_SYSERR_MEM_EXHAUSTED: "System memory exhausted",
    }

    interface_types = {
        IF_TYPE_USB: "usb",
        IF_TYPE_UART: "uart",
        IF_TYPE_W80211: "mw",
        IF_TYPE_BLE: "ble",
        IF_TYPE_LORA: "lora",
        IF_TYPE_ETHERNET: "eth",
        IF_TYPE_WIFI: "wifi",
        IF_TYPE_TCP: "tcp",
        IF_TYPE_UDP: "udp",
        IF_TYPE_IR: "ir",
        IF_TYPE_AFSK: "afsk",
        IF_TYPE_GPIO: "gpio",
        IF_TYPE_SPI: "spi",
        IF_TYPE_I2C: "i2c",
        IF_TYPE_CAN: "can",
        IF_TYPE_DMA: "dma",
    }

    channel_descriptions = {
        1: "Channel 1 (2412 MHz)",
        2: "Channel 2 (2417 MHz)",
        3: "Channel 3 (2422 MHz)",
        4: "Channel 4 (2427 MHz)",
        5: "Channel 5 (2432 MHz)",
        6: "Channel 6 (2437 MHz)",
        7: "Channel 7 (2442 MHz)",
        8: "Channel 8 (2447 MHz)",
        9: "Channel 9 (2452 MHz)",
        10: "Channel 10 (2457 MHz)",
        11: "Channel 11 (2462 MHz)",
        12: "Channel 12 (2467 MHz)",
        13: "Channel 13 (2472 MHz)",
        14: "Channel 14 (2484 MHz)",
    }

    LOG_FORCE    = 0
    LOG_CRITICAL = 1
    LOG_ERROR    = 2
    LOG_WARNING  = 3
    LOG_NOTICE   = 4
    LOG_INFO     = 5
    LOG_VERBOSE  = 6
    LOG_DEBUG    = 7
    LOG_EXTREME  = 8
    LOG_SYSTEM   = 9

    levels = {
        LOG_FORCE: "Forced",
        LOG_CRITICAL: "Critical",
        LOG_ERROR: "Error",
        LOG_WARNING: "Warning",
        LOG_NOTICE: "Notice",
        LOG_INFO: "Info",
        LOG_VERBOSE: "Verbose",
        LOG_DEBUG: "Debug",
        LOG_EXTREME: "Extreme",
        LOG_SYSTEM: "System",
    }

    task_descriptions = {
        "taskLVGL": "Driver: UI Renderer",
        "ui_service": "Service: User Interface",
        "TinyUSB":  "Driver: USB",
        "drv_w80211": "Driver: W802.11",
        "system_stats": "System: Stats",
        "core": "System: Core",
        "protocol_wdcl": "Protocol: WDCL",
        "protocol_weave": "Protocol: Weave",
        "tiT": "Protocol: TCP/IP",
        "ipc0": "System: CPU 0 IPC",
        "ipc1": "System: CPU 1 IPC",
        "esp_timer": "Driver: Timers",
        "Tmr Svc": "Service: Timers",
        "kernel_logger": "Service: Logging",
        "remote_display": "Service: Remote Display",
        "wifi": "System: WiFi Hardware",
        "sys_evt": "System: Kernel Events",
    }

    @staticmethod
    def level(level):
        if level in Evt.levels: return Evt.levels[level]
        else: return "Unknown"

class LogFrame():
    timestamp = None
    level = None
    event = None
    data = b""

    def __init__(self, timestamp=None, level=None, event=None, data=b""):
        self.timestamp = timestamp; self.level = level
        self.event = event; self.data = data

class WeaveEndpoint():
    QUEUE_LEN = 1024

    def __init__(self, endpoint_addr):
        self.endpoint_addr = endpoint_addr
        self.alive = time.time()
        self.via = None
        self.received = deque(maxlen=WeaveEndpoint.QUEUE_LEN)

    def receive(self, data):
        self.received.append(data)

class WeaveDevice():
    STATLEN_MAX            = 120
    STAT_UPDATE_THROTTLE   = 0.5

    WEAVE_SWITCH_ID_LEN    = 4
    WEAVE_ENDPOINT_ID_LEN  = 8
    WEAVE_FLOWSEQ_LEN      = 2
    WEAVE_HMAC_LEN         = 8
    WEAVE_AUTH_LEN         = WEAVE_ENDPOINT_ID_LEN+WEAVE_HMAC_LEN

    WEAVE_PUBKEY_SIZE      = 32
    WEAVE_PRVKEY_SIZE      = 64
    WEAVE_SIGNATURE_LEN    = 64

    def __init__(self, as_interface=False, rns_interface=None):
        self.identity        = None
        self.receiver        = None
        self.switch_id       = None
        self.endpoint_id     = None
        self.owner           = None
        self.rns_interface   = rns_interface
        self.as_interface    = as_interface
        self.endpoints       = {}
        self.active_tasks    = {}
        self.cpu_load        = 0
        self.memory_total    = 0
        self.memory_free     = 0
        self.memory_used     = 0
        self.memory_used_pct = 0
        self.log_queue       = deque()
        self.memory_stats    = deque(maxlen=WeaveDevice.STATLEN_MAX)
        self.cpu_stats       = deque(maxlen=WeaveDevice.STATLEN_MAX)
        self.display_buffer  = bytearray(0)
        self.update_display  = False

        self.next_update_memory = 0
        self.next_update_cpu    = 0

    def wdcl_send(self, packet_type, data):
        if not self.switch_id:
            if self.as_interface: RNS.log("Attempt to transmit on {self} while remote Weave device identity is unknown", RNS.LOG_ERROR)
            else: self.receiver.log("Error: Attempt to transmit while remote Weave device identity is unknown")
        else:
            frame  = self.switch_id
            frame += bytes([packet_type])
            frame += data
            self.connection.process_outgoing(frame)

    def wdcl_broadcast(self, packet_type, data):
        frame  = WDCL.WDCL_BROADCAST
        frame += bytes([packet_type])
        frame += data
        self.connection.process_outgoing(frame)

    def wdcl_send_command(self, command, data):
        frame  = b""
        frame += bytes([command>>8, (command & 0xFF)])
        frame += data
        self.wdcl_send(WDCL.WDCL_T_CMD, frame)

    def discover(self):
        self.wdcl_broadcast(WDCL.WDCL_T_DISCOVER, self.connection.switch_id)

    def handshake(self):
        if self.identity == None:
            if self.as_interface: RNS.log("Attempt to perform handshake on {self} before remote device discovery completion", RNS.LOG_ERROR)
            else: self.receiver.log("Attempt to perform handshake before remote device discovery completion")
        else:
            signed_id = self.switch_id
            signature = self.connection.switch_identity.sign(signed_id)
            data      = self.connection.switch_pub_bytes
            data     += signature
            self.wdcl_send(WDCL.WDCL_T_CONNECT, data)
            if self.as_interface: RNS.log(f"WDCL connection handshake sent", RNS.LOG_VERBOSE)
            else: self.receiver.log("Connection handshake sent")

    def capture_stats_cpu(self):
        self.cpu_stats.append({"timestamp": time.time(), "cpu_load": self.cpu_load})
        if self.receiver and self.receiver.ready and len(self.memory_stats) > 1: self.receiver.stats_update("cpu")

    def capture_stats_memory(self):
        self.memory_stats.append({"timestamp": time.time(), "memory_used": self.memory_used})
        if self.receiver and self.receiver.ready and len(self.memory_stats) > 1: self.receiver.stats_update("memory")

    def get_cpu_stats(self):
        tbegin = None
        stats = {"timestamps": [], "values": [], "max": 100, "unit": "%"}
        for i in range(0, len(self.cpu_stats)):
            if tbegin == None: tbegin = self.cpu_stats[len(self.cpu_stats)-1]["timestamp"]
            stats["timestamps"].append(self.cpu_stats[i]["timestamp"]-tbegin)
            stats["values"].append(self.cpu_stats[i]["cpu_load"])

        return stats

    def get_memory_stats(self):
        tbegin = None
        stats = {"timestamps": [], "values": [], "max": self.memory_total, "unit": "B"}
        for i in range(0, len(self.memory_stats)):
            if tbegin == None: tbegin = self.memory_stats[len(self.memory_stats)-1]["timestamp"]
            stats["timestamps"].append(self.memory_stats[i]["timestamp"]-tbegin)
            stats["values"].append(self.memory_stats[i]["memory_used"])

        return stats

    def get_active_tasks(self):
        active_tasks = {}
        now = time.time()
        for task_id in self.active_tasks:
            if not task_id.startswith("IDLE"):
                task_description = task_id
                if task_id in Evt.task_descriptions: task_description = Evt.task_descriptions[task_id]
                if now - self.active_tasks[task_id]["timestamp"] < 5:
                    active_tasks[task_description] = self.active_tasks[task_id]

        return active_tasks

    def disconnect_display(self):
        self.wdcl_send_command(Cmd.WDCL_CMD_REMOTE_DISPLAY, bytes([0x00]))
        self.update_display = False

    def connect_display(self):
        self.wdcl_send_command(Cmd.WDCL_CMD_REMOTE_DISPLAY, bytes([0x01]))
        self.update_display = True

    def endpoint_alive(self, endpoint_id):
        if not endpoint_id in self.endpoints: self.endpoints[endpoint_id] = WeaveEndpoint(endpoint_id)
        else: self.endpoints[endpoint_id].alive = time.time()

        if self.as_interface: self.rns_interface.add_peer(endpoint_id)

    def endpoint_via(self, endpoint_id, via_switch_id):
        if endpoint_id in self.endpoints: self.endpoints[endpoint_id].via = via_switch_id
        if self.as_interface: self.rns_interface.endpoint_via(endpoint_id, via_switch_id)

    def deliver_packet(self, endpoint_id, data):
        packet_data = endpoint_id+data
        self.wdcl_send_command(Cmd.WDCL_CMD_ENDPOINT_PKT, packet_data)

    def received_packet(self, source, data):
        self.endpoint_alive(source)
        if self.as_interface:
            self.rns_interface.process_incoming(data, source)

    def incoming_frame(self, data):
        if len(data) > self.WEAVE_SWITCH_ID_LEN+2 and data[self.WEAVE_SWITCH_ID_LEN] == WDCL.WDCL_T_ENDPOINT_PKT and data[:self.WEAVE_SWITCH_ID_LEN] == self.connection.switch_id:
            payload = data[self.WEAVE_SWITCH_ID_LEN+1:-self.WEAVE_ENDPOINT_ID_LEN]
            src_endpoint = data[-self.WEAVE_ENDPOINT_ID_LEN:]
            self.received_packet(src_endpoint, payload)

        elif len(data) > self.WEAVE_SWITCH_ID_LEN+1 and data[self.WEAVE_SWITCH_ID_LEN] == WDCL.WDCL_T_DISCOVER:
            discovery_response_len = self.WEAVE_SWITCH_ID_LEN+1+self.WEAVE_PUBKEY_SIZE+self.WEAVE_SIGNATURE_LEN
            if len(data) == discovery_response_len:
                signed_id        = data[:self.WEAVE_SWITCH_ID_LEN]
                remote_pub_key   = data[self.WEAVE_SWITCH_ID_LEN+1:self.WEAVE_SWITCH_ID_LEN+1+self.WEAVE_PUBKEY_SIZE]
                remote_switch_id = remote_pub_key[-4:]
                remote_signature = data[self.WEAVE_SWITCH_ID_LEN+1+self.WEAVE_PUBKEY_SIZE:self.WEAVE_SWITCH_ID_LEN+1+self.WEAVE_PUBKEY_SIZE+self.WEAVE_SIGNATURE_LEN]
                remote_identity = RNS.Identity(create_keys=False)
                remote_identity.load_public_key(remote_pub_key*2)
                if remote_identity.validate(remote_signature, signed_id):
                    if self.as_interface: RNS.log(f"Remote Weave device {RNS.hexrep(remote_switch_id)} discovered", RNS.LOG_VERBOSE)
                    else: self.receiver.log(f"Remote Weave device {RNS.hexrep(remote_switch_id)} discovered")
                    self.identity = remote_identity
                    self.switch_id = remote_switch_id
                    self.handshake()
                else:
                    if self.as_interface: RNS.LOG("Invalid remote device discovery response received", RNS.LOG_ERROR)
                    else: self.receiver.log("Invalid remote device discovery response received")

        elif len(data) > self.WEAVE_SWITCH_ID_LEN+1 and data[self.WEAVE_SWITCH_ID_LEN] == WDCL.WDCL_T_LOG:
            fd  = data[self.WEAVE_SWITCH_ID_LEN+2:]
            ts  = fd[1] << 24 | fd[2] << 16 | fd[3] << 8 | fd[4]
            lvl = fd[5]; evt = fd[6] << 8 | fd[7]; data = fd[8:]
            self.log_handle(LogFrame(timestamp=ts/1000.0, level=lvl, event=evt, data=data))

        elif len(data) > self.WEAVE_SWITCH_ID_LEN+10 and data[self.WEAVE_SWITCH_ID_LEN] == WDCL.WDCL_T_DISP:
            fd  = data[self.WEAVE_SWITCH_ID_LEN+1:]
            cf  = fd[0]
            ofs = fd[1] << 24 | fd[2] << 16 | fd[3] << 8 | fd[4]
            dsz = fd[5] << 24 | fd[6] << 16 | fd[7] << 8 | fd[8]
            fbf = fd[9:]

            w = 128; h = 64

            if dsz > len(self.display_buffer): self.display_buffer = bytearray(dsz)
            self.display_buffer[ofs:ofs+len(fbf)] = fbf

            if self.receiver and self.receiver.ready and ofs+len(fbf) == dsz:
                if self.update_display: self.receiver.display_update(self.display_buffer, w, h)

    def log_handle(self, frame):
        # Handle system event signalling
        if frame.event == Evt.ET_PROTO_WDCL_CONNECTION: self.connection.wdcl_connected = True
        if frame.event == Evt.ET_PROTO_WDCL_HOST_ENDPOINT and len(frame.data) == self.WEAVE_ENDPOINT_ID_LEN: self.endpoint_id = frame.data
        if frame.event == Evt.ET_PROTO_WEAVE_EP_ALIVE and len(frame.data) == self.WEAVE_ENDPOINT_ID_LEN: self.endpoint_alive(frame.data)
        if frame.event == Evt.ET_PROTO_WEAVE_EP_VIA and len(frame.data) == self.WEAVE_ENDPOINT_ID_LEN+self.WEAVE_SWITCH_ID_LEN: self.endpoint_via(frame.data[:self.WEAVE_ENDPOINT_ID_LEN], frame.data[self.WEAVE_ENDPOINT_ID_LEN:])
        elif frame.event == Evt.ET_STAT_TASK_CPU: self.active_tasks[frame.data[1:].decode("utf-8")] = { "cpu_load": frame.data[0], "timestamp": time.time() }
        elif frame.event == Evt.ET_STAT_CPU: 
            self.cpu_load = frame.data[0]
            self.capture_stats_cpu()
        elif frame.event == Evt.ET_STAT_MEMORY:
            self.memory_free     = int.from_bytes(frame.data[:4])
            self.memory_total    = int.from_bytes(frame.data[4:])
            self.memory_used     = self.memory_total-self.memory_free
            self.memory_used_pct = round((self.memory_used/self.memory_total)*100, 2)
            self.capture_stats_memory()

        # Handle generic messages and unmapped events
        else:
            ts = RNS.prettytime(frame.timestamp)
            if frame.event == Evt.ET_MSG:
                if len(frame.data): data_string = frame.data.decode("utf-8")
                else: data_string = ""
                rendered = f"[{ts}] [{Evt.level(frame.level)}]: {data_string}"

            else:
                if frame.event in Evt.event_descriptions: event_description = Evt.event_descriptions[frame.event]
                else: event_description = f"0x{RNS.hexrep(frame.event, delimit=False)}"

                if frame.event == Evt.ET_INTERFACE_REGISTERED:
                    if len(frame.data) >= 2:
                        interface_index = frame.data[0]; interface_type = frame.data[1]
                        type_name = "phy"
                        if interface_type in Evt.interface_types: type_name = Evt.interface_types[interface_type]
                        data_string = f": {type_name}{interface_index}"
                    else: data_string = ""
                else:
                    if len(frame.data):
                        data_string = f": {RNS.hexrep(frame.data)}"
                        if   frame.event == Evt.ET_DRV_USB_CDC_CONNECTED:
                            if   frame.data[0] == 0x01: data_string = ": Connected"
                            elif frame.data[0] == 0x00: data_string = ": Disconnected"
                        elif frame.event == Evt.ET_DRV_W80211_CHANNEL:
                            if   frame.data[0] in Evt.channel_descriptions: data_string = f": {Evt.channel_descriptions[frame.data[0]]}"
                            else:                                           data_string = f": {RNS.hexrep(frame.data)}"
                        elif frame.event == Evt.ET_DRV_W80211_POWER:
                            tx_power = frame.data[0]*0.25
                            data_string = f": {tx_power} dBm ({int(10**(tx_power/10))} mW)"
                        elif frame.event >= Evt.ET_CORE_INIT and frame.event <= Evt.ET_PROTO_WEAVE_RUNNING:
                            if   frame.data[0] == 0x01: data_string = ": Success"
                            elif frame.data[0] == 0x00:
                                if frame.level == Evt.LOG_ERROR: data_string = ": Failure"
                                else:                            data_string = ": Stopped"
                            else:                       data_string = f": {RNS.hexrep(frame.data)}"
                        
                    else: data_string = ""

                rendered = f"[{ts}] [{Evt.level(frame.level)}] [{event_description}]{data_string}"
            
            if self.as_interface:
                RNS.log(f"{self.rns_interface}: {rendered}", RNS.LOG_EXTREME)
            else:
                if self.receiver and self.receiver.ready:
                    while len(self.log_queue): self.receiver.log(self.log_queue.pop())
                    self.receiver.log(rendered)
                else: self.log_queue.append(rendered)

class WeaveInterface(Interface):
    HW_MTU = 1024
    FIXED_MTU = True

    DEFAULT_IFAC_SIZE  = 16
    PEERING_TIMEOUT    = 20.0
    BITRATE_GUESS      = 250*1000

    MULTI_IF_DEQUE_LEN = 48
    MULTI_IF_DEQUE_TTL = 0.75

    @property
    def cpu_load(self):
        if not self.device: return None
        else: return self.device.cpu_load

    @property
    def mem_load(self):
        if not self.device: return None
        else: return self.device.memory_used_pct

    @property
    def switch_id(self):
        if not self.device: return None
        else: return self.device.switch_id

    @property
    def endpoint_id(self):
        if not self.device: return None
        else: return self.device.endpoint_id

    def __init__(self, owner, configuration):
        c                      = Interface.get_config_obj(configuration)
        name                   = c["name"]
        port                   = c["port"]
        configured_bitrate     = c["configured_bitrate"] if "configured_bitrate" in c else None

        from RNS.Interfaces import netinfo
        super().__init__()
        self.netinfo = netinfo

        self.HW_MTU = WeaveInterface.HW_MTU
        self.IN  = True
        self.OUT = False
        self.name = name
        self.port = port
        self.switch_identity = RNS.Identity()
        self.owner = owner
        self.hw_errors = []
        self._online = False
        self.final_init_done = False
        self.peers = {}
        self.timed_out_interfaces = {}
        self.spawned_interfaces = {}
        self.write_lock = threading.Lock()
        self.mif_deque = deque(maxlen=WeaveInterface.MULTI_IF_DEQUE_LEN)
        self.mif_deque_times = deque(maxlen=WeaveInterface.MULTI_IF_DEQUE_LEN)

        self.announce_rate_target = None
        self.peer_job_interval = WeaveInterface.PEERING_TIMEOUT*1.1
        self.peering_timeout   = WeaveInterface.PEERING_TIMEOUT

        self.receives = True
        if configured_bitrate != None: self.bitrate = configured_bitrate
        else: self.bitrate = WeaveInterface.BITRATE_GUESS

    def final_init(self):
        self.device = WeaveDevice(as_interface=True, rns_interface=self)
        self.connection = WDCL(owner=self, device=self.device, port=self.port, as_interface=True)

        job_thread = threading.Thread(target=self.peer_jobs)
        job_thread.daemon = True
        job_thread.start()

        self._online = True
        self.final_init_done = True

    def peer_jobs(self):
        while True:
            time.sleep(self.peer_job_interval)
            now = time.time()
            timed_out_peers = []

            # Check for timed out peers
            for peer_addr in self.peers:
                peer = self.peers[peer_addr]
                last_heard = peer[1]
                if now > last_heard+self.peering_timeout:
                    timed_out_peers.append(peer_addr)

            # Remove any timed out peers
            for peer_addr in timed_out_peers:
                removed_peer = self.peers.pop(peer_addr)
                if peer_addr in self.spawned_interfaces:
                    spawned_interface = self.spawned_interfaces[peer_addr]
                    spawned_interface.detach()
                    spawned_interface.teardown()
                RNS.log(str(self)+" removed peer "+RNS.hexrep(peer_addr)+" on "+RNS.hexrep(removed_peer[0]), RNS.LOG_DEBUG)
            
    @property
    def peer_count(self):
        return len(self.spawned_interfaces)

    def endpoint_via(self, endpoint_addr, via_switch_addr):
        if endpoint_addr in self.peers: self.peers[endpoint_addr][2].via_switch_id = via_switch_addr

    def add_peer(self, endpoint_addr):    
        if not endpoint_addr in self.peers:
            spawned_interface = WeaveInterfacePeer(self, endpoint_addr)
            spawned_interface.OUT = self.OUT
            spawned_interface.IN  = self.IN
            spawned_interface.parent_interface = self
            spawned_interface.bitrate = self.bitrate
            
            spawned_interface.ifac_size = self.ifac_size
            spawned_interface.ifac_netname = self.ifac_netname
            spawned_interface.ifac_netkey = self.ifac_netkey
            if spawned_interface.ifac_netname != None or spawned_interface.ifac_netkey != None:
                ifac_origin = b""
                if spawned_interface.ifac_netname != None:
                    ifac_origin += RNS.Identity.full_hash(spawned_interface.ifac_netname.encode("utf-8"))
                if spawned_interface.ifac_netkey != None:
                    ifac_origin += RNS.Identity.full_hash(spawned_interface.ifac_netkey.encode("utf-8"))

                ifac_origin_hash = RNS.Identity.full_hash(ifac_origin)
                spawned_interface.ifac_key = RNS.Cryptography.hkdf(
                    length=64,
                    derive_from=ifac_origin_hash,
                    salt=RNS.Reticulum.IFAC_SALT,
                    context=None
                )
                spawned_interface.ifac_identity = RNS.Identity.from_bytes(spawned_interface.ifac_key)
                spawned_interface.ifac_signature = spawned_interface.ifac_identity.sign(RNS.Identity.full_hash(spawned_interface.ifac_key))

            spawned_interface.announce_rate_target = self.announce_rate_target
            spawned_interface.announce_rate_grace = self.announce_rate_grace
            spawned_interface.announce_rate_penalty = self.announce_rate_penalty
            spawned_interface.mode = self.mode
            spawned_interface.HW_MTU = self.HW_MTU
            spawned_interface._online = True
            RNS.Transport.interfaces.append(spawned_interface)
            if endpoint_addr in self.spawned_interfaces:
                self.spawned_interfaces[endpoint_addr].detach()
                self.spawned_interfaces[endpoint_addr].teardown()
                self.spawned_interfaces.pop(spawned_interface)

            self.spawned_interfaces[endpoint_addr] = spawned_interface
            self.peers[endpoint_addr] = [endpoint_addr, time.time(), spawned_interface]

            RNS.log(f"{self} added peer {RNS.hexrep(endpoint_addr)}", RNS.LOG_DEBUG)
        else:
            self.refresh_peer(endpoint_addr)

    def refresh_peer(self, endpoint_addr):
        try:
            self.peers[endpoint_addr][1] = time.time()
        except Exception as e:
            RNS.log(f"An error occurred while refreshing peer {RNS.hexrep(endpoint_addr)} on {self}: {e}", RNS.LOG_ERROR)

    def process_incoming(self, data, endpoint_addr=None):
        if self.online and endpoint_addr in self.spawned_interfaces:
            self.spawned_interfaces[endpoint_addr].process_incoming(data, endpoint_addr)

    def process_outgoing(self,data):
        pass

    def detach(self):
        self._online = False

    @property
    def online(self):
        if not self._online: return False
        else: return self.connection.online

    @online.setter
    def online(self, value):
        self._online = value
    
    def __str__(self):
        return "WeaveInterface["+self.name+"]"

class WeaveInterfacePeer(Interface):

    def __init__(self, owner, endpoint_addr):
        super().__init__()
        self.owner = owner
        self.parent_interface = owner
        self.endpoint_addr = endpoint_addr
        self.via_switch_id = None
        self.peer_addr = None
        self.addr_info = None
        self.HW_MTU = self.owner.HW_MTU
        self.FIXED_MTU = self.owner.FIXED_MTU
        self._online = False

    def __str__(self):
        return f"WeaveInterfacePeer[{RNS.hexrep(self.endpoint_addr)}]"

    @property
    def online(self):
        if not self._online or not self.owner: return false
        else: return self.owner.online

    @online.setter
    def online(self, value):
        self._online = value

    def process_incoming(self, data, endpoint_addr=None):
        if self.online:
            data_hash = RNS.Identity.full_hash(data)
            deque_hit = False
            if data_hash in self.owner.mif_deque:
                for te in self.owner.mif_deque_times:
                    if te[0] == data_hash and time.time() < te[1]+WeaveInterface.MULTI_IF_DEQUE_TTL:
                        deque_hit = True
                        break

            if not deque_hit:
                self.owner.refresh_peer(self.endpoint_addr)
                self.owner.mif_deque.append(data_hash)
                self.owner.mif_deque_times.append([data_hash, time.time()])
                self.rxb += len(data)
                self.owner.rxb += len(data)
                self.owner.owner.inbound(data, self)

    def process_outgoing(self, data):
        if self.online:
            with self.owner.write_lock:
                try:
                    self.owner.device.deliver_packet(self.endpoint_addr, data)
                    self.txb += len(data)
                    self.owner.txb += len(data)
                except Exception as e:
                    RNS.log("Could not transmit on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    def detach(self):
        self._online = False
        self.detached = True
        
    def teardown(self):
        if not self.detached:
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down.", RNS.LOG_ERROR)
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

        else: RNS.log("The interface "+str(self)+" is being torn down.", RNS.LOG_VERBOSE)

        self._online = False
        self.OUT = False
        self.IN = False

        if self.endpoint_addr in self.owner.spawned_interfaces:
            try: self.owner.spawned_interfaces.pop(self.endpoint_addr)
            except Exception as e:
                RNS.log(f"Could not remove {self} from parent interface on detach. The contained exception was: {e}", RNS.LOG_ERROR)

        if self in RNS.Transport.interfaces:
            RNS.Transport.interfaces.remove(self)
