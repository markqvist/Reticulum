# MIT License - Copyright (c) 2024 Mark Qvist / unsigned.io

# This example illustrates creating a custom interface
# definition, that can be loaded and used by Reticulum at
# runtime. Any number of custom interfaces can be created
# and loaded. To use the interface place it in the folder
# ~/.reticulum/interfaces, and add an interface entry to
# your Reticulum configuration file similar to this:

#  [[Example Custom Interface]]
#    type = ExampleInterface
#    enabled = no
#    mode = gateway
#    port = /dev/ttyUSB0
#    speed = 115200
#    databits = 8
#    parity = none
#    stopbits = 1

from time import sleep
import sys
import threading
import time

# This HDLC helper class is used by the interface
# to delimit and packetize data over the physical
# medium - in this case a serial connection.
class HDLC():
    # This example interface packetizes data using
    # simplified HDLC framing, similar to PPP
    FLAG     = 0x7E
    ESC      = 0x7D
    ESC_MASK = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

# Let's define our custom interface class. It must
# be a sub-class of the RNS "Interface" class.
class ExampleInterface(Interface):
    # All interface classes must define a default
    # IFAC size, used in IFAC setup when the user
    # has not specified a custom IFAC size. This
    # option is specified in bytes.
    DEFAULT_IFAC_SIZE = 8

    # The following properties are local to this
    # particular interface implementation.
    owner    = None
    port     = None
    speed    = None
    databits = None
    parity   = None
    stopbits = None
    serial   = None

    # All Reticulum interfaces must have an __init__
    # method that takes 2 positional arguments:
    # The owner RNS Transport instance, and a dict
    # of configuration values.
    def __init__(self, owner, configuration):

        # The following lines demonstrate handling
        # potential dependencies required for the
        # interface to function correctly.
        import importlib
        if importlib.util.find_spec('serial') != None:
            import serial
        else:
            RNS.log("Using this interface requires a serial communication module to be installed.", RNS.LOG_CRITICAL)
            RNS.log("You can install one with the command: python3 -m pip install pyserial", RNS.LOG_CRITICAL)
            RNS.panic()

        # We start out by initialising the super-class
        super().__init__()

        # To make sure the configuration data is in the
        # correct format, we parse it through the following
        # method on the generic Interface class. This step
        # is required to ensure compatibility on all the
        # platforms that Reticulum supports.
        ifconf    = Interface.get_config_obj(configuration)

        # Read the interface name from the configuration
        # and set it on our interface instance.
        name      = ifconf["name"]
        self.name = name

        # We read configuration parameters from the supplied
        # configuration data, and provide default values in
        # case any are missing.
        port      = ifconf["port"] if "port" in ifconf else None
        speed     = int(ifconf["speed"]) if "speed" in ifconf else 9600
        databits  = int(ifconf["databits"]) if "databits" in ifconf else 8
        parity    = ifconf["parity"] if "parity" in ifconf else "N"
        stopbits  = int(ifconf["stopbits"]) if "stopbits" in ifconf else 1

        # In case no port is specified, we abort setup by
        # raising an exception.
        if port == None:
            raise ValueError(f"No port specified for {self}")

        # All interfaces must supply a hardware MTU value
        # to the RNS Transport instance. This value should
        # be the maximum data packet payload size that the
        # underlying medium is capable of handling in all
        # cases without any segmentation.
        self.HW_MTU = 564

        # We initially set the "online" property to false,
        # since the interface has not actually been fully
        # initialised and connected yet.
        self.online   = False

        # In this case, we can also set the indicated bit-
        # rate of the interface to the serial port speed.
        self.bitrate  = speed
        
        # Configure internal properties on the interface
        # according to the supplied configuration.
        self.pyserial = serial
        self.serial   = None
        self.owner    = owner
        self.port     = port
        self.speed    = speed
        self.databits = databits
        self.parity   = serial.PARITY_NONE
        self.stopbits = stopbits
        self.timeout  = 100

        if parity.lower() == "e" or parity.lower() == "even":
            self.parity = serial.PARITY_EVEN

        if parity.lower() == "o" or parity.lower() == "odd":
            self.parity = serial.PARITY_ODD

        # Since all required parameters are now configured,
        # we will try opening the serial port.
        try:
            self.open_port()
        except Exception as e:
            RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
            raise e

        # If opening the port succeeded, run any post-open
        # configuration required.
        if self.serial.is_open:
            self.configure_device()
        else:
            raise IOError("Could not open serial port")

    # Open the serial port with supplied configuration
    # parameters and store a reference to the open port.
    def open_port(self):
        RNS.log("Opening serial port "+self.port+"...", RNS.LOG_VERBOSE)
        self.serial = self.pyserial.Serial(
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

    # The only thing required after opening the port
    # is to wait a small amount of time for the
    # hardware to initialise and then start a thread
    # that reads any incoming data from the device.
    def configure_device(self):
        sleep(0.5)
        thread = threading.Thread(target=self.read_loop)
        thread.daemon = True
        thread.start()
        self.online = True
        RNS.log("Serial port "+self.port+" is now open", RNS.LOG_VERBOSE)


    # This method will be called from our read-loop
    # whenever a full packet has been received over
    # the underlying medium.
    def process_incoming(self, data):
        # Update our received bytes counter
        self.rxb += len(data)            

        # And send the data packet to the Transport
        # instance for processing.
        self.owner.inbound(data, self)

    # The running Reticulum Transport instance will
    # call this method on the interface whenever the
    # interface must transmit a packet.
    def process_outgoing(self,data):
        if self.online:
            # First, escape and packetize the data
            # according to HDLC framing.
            data = bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])

            # Then write the framed data to the port
            written = self.serial.write(data)

            # Update the transmitted bytes counter
            # and ensure that all data was written
            self.txb += len(data)            
            if written != len(data):
                raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))

    # This read loop runs in a thread and continously
    # receives bytes from the underlying serial port.
    # When a full packet has been received, it will
    # be sent to the process_incoming methed, which
    # will in turn pass it to the Transport instance.
    def read_loop(self):
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
                        self.process_incoming(data_buffer)
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
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is now offline.", RNS.LOG_ERROR)
            
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)

        self.online = False
        self.serial.close()
        self.reconnect_port()

    # This method handles serial port disconnects.
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

    # Signal to Reticulum that this interface should
    # not perform any ingress limiting.
    def should_ingress_limit(self):
        return False

    # We must provide a string representation of this
    # interface, that is used whenever the interface
    # is printed in logs or external programs.
    def __str__(self):
        return "ExampleInterface["+self.name+"]"

# Finally, register the defined interface class as the
# target class for Reticulum to use as an interface
interface_class = ExampleInterface