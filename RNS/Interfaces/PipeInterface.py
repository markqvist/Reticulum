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

from .Interface import Interface
from time import sleep
import sys
import threading
import time
import RNS

import subprocess
import shlex

class HDLC():
    # The Pipe Interface packetizes data using
    # simplified HDLC framing, similar to PPP
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

class PipeInterface(Interface):
    MAX_CHUNK = 32768
    BITRATE_GUESS = 1*1000*1000

    owner    = None
    command  = None
    
    def __init__(self, owner, name, command, respawn_delay):
        if respawn_delay == None:
            respawn_delay = 5

        self.rxb = 0
        self.txb = 0

        self.HW_MTU = 1064
        
        self.owner    = owner
        self.name     = name
        self.command  = command
        self.process  = None
        self.timeout  = 100
        self.online   = False
        self.pipe_is_open = False
        self.bitrate  = PipeInterface.BITRATE_GUESS
        self.respawn_delay = respawn_delay

        try:
            self.open_pipe()

        except Exception as e:
            RNS.log("Could connect pipe for interface "+str(self), RNS.LOG_ERROR)
            raise e

        if self.pipe_is_open:
            self.configure_pipe()
        else:
            raise IOError("Could not connect pipe")


    def open_pipe(self):
        RNS.log("Connecting subprocess pipe for "+str(self)+"...", RNS.LOG_VERBOSE)
        
        try:
            self.process = subprocess.Popen(shlex.split(self.command), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            self.pipe_is_open = True
        except Exception as e:
            raise e
            self.pipe_is_open = False


    def configure_pipe(self):
        sleep(0.01)
        thread = threading.Thread(target=self.readLoop)
        thread.daemon = True
        thread.start()
        self.online = True
        RNS.log("Subprocess pipe for "+str(self)+" is now connected", RNS.LOG_VERBOSE)


    def processIncoming(self, data):
        self.rxb += len(data)            
        self.owner.inbound(data, self)


    def processOutgoing(self,data):
        if self.online:
            data = bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])
            written = self.process.stdin.write(data)
            self.process.stdin.flush()
            self.txb += len(data)            
            if written != len(data):
                raise IOError("Pipe interface only wrote "+str(written)+" bytes of "+str(len(data)))


    def readLoop(self):
        try:
            in_frame = False
            escape = False
            data_buffer = b""
            last_read_ms = int(time.time()*1000)

            while True:
                process_output = self.process.stdout.read(1)
                if len(process_output) == 0 and self.process.poll() is not None:
                    break

                else:
                    byte = ord(process_output)
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

            RNS.log("Subprocess terminated on "+str(self))
            self.process.kill()
                    
        except Exception as e:
            self.online = False
            try:
                self.process.kill()
            except Exception as e:
                pass

            RNS.log("A pipe error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is now offline.", RNS.LOG_ERROR)
            
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the interface periodically.", RNS.LOG_ERROR)

        self.online = False
        self.reconnect_pipe()

    def reconnect_pipe(self):
        while not self.online:
            try:
                time.sleep(self.respawn_delay)
                RNS.log("Attempting to respawn subprocess for "+str(self)+"...", RNS.LOG_VERBOSE)
                self.open_pipe()
                if self.pipe_is_open:
                    self.configure_pipe()
            except Exception as e:
                RNS.log("Error while spawning subprocess, the contained exception was: "+str(e), RNS.LOG_ERROR)

        RNS.log("Reconnected pipe for "+str(self))

    def __str__(self):
        return "PipeInterface["+self.name+"]"
