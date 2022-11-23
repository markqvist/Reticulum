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

import os
import sys
import glob
import time
import random
import threading

from ._version import __version__

from .Reticulum import Reticulum
from .Identity import Identity
from .Link import Link, RequestReceipt
from .Transport import Transport
from .Destination import Destination
from .Packet import Packet
from .Packet import PacketReceipt
from .Resource import Resource, ResourceAdvertisement
from .Cryptography import HKDF
from .Cryptography import Hashes

modules = glob.glob(os.path.dirname(__file__)+"/*.py")
__all__ = [ os.path.basename(f)[:-3] for f in modules if not f.endswith('__init__.py')]

LOG_CRITICAL = 0
LOG_ERROR    = 1
LOG_WARNING  = 2
LOG_NOTICE   = 3
LOG_INFO     = 4
LOG_VERBOSE  = 5
LOG_DEBUG    = 6
LOG_EXTREME  = 7

LOG_STDOUT   = 0x91
LOG_FILE     = 0x92

LOG_MAXSIZE  = 5*1024*1024

loglevel        = LOG_NOTICE
logfile         = None
logdest         = LOG_STDOUT
logtimefmt      = "%Y-%m-%d %H:%M:%S"
compact_log_fmt = False

instance_random = random.Random()
instance_random.seed(os.urandom(10))

_always_override_destination = False

logging_lock = threading.Lock()

def loglevelname(level):
    if (level == LOG_CRITICAL):
        return "Critical"
    if (level == LOG_ERROR):
        return "Error"
    if (level == LOG_WARNING):
        return "Warning"
    if (level == LOG_NOTICE):
        return "Notice"
    if (level == LOG_INFO):
        return "Info"
    if (level == LOG_VERBOSE):
        return "Verbose"
    if (level == LOG_DEBUG):
        return "Debug"
    if (level == LOG_EXTREME):
        return "Extra"
    
    return "Unknown"

def version():
    return __version__

def host_os():
    from .vendor.platformutils import get_platform
    return get_platform()

def timestamp_str(time_s):
    timestamp = time.localtime(time_s)
    return time.strftime(logtimefmt, timestamp)

def log(msg, level=3, _override_destination = False):
    global _always_override_destination, compact_log_fmt
    
    if loglevel >= level:
        if not compact_log_fmt:
            logstring = "["+timestamp_str(time.time())+"] ["+loglevelname(level)+"] "+msg
        else:
            logstring = "["+timestamp_str(time.time())+"] "+msg

        logging_lock.acquire()

        if (logdest == LOG_STDOUT or _always_override_destination or _override_destination):
            print(logstring)
            logging_lock.release()

        elif (logdest == LOG_FILE and logfile != None):
            try:
                file = open(logfile, "a")
                file.write(logstring+"\n")
                file.close()
                
                if os.path.getsize(logfile) > LOG_MAXSIZE:
                    prevfile = logfile+".1"
                    if os.path.isfile(prevfile):
                        os.unlink(prevfile)
                    os.rename(logfile, prevfile)

                logging_lock.release()
            except Exception as e:
                logging_lock.release()
                _always_override_destination = True
                log("Exception occurred while writing log message to log file: "+str(e), LOG_CRITICAL)
                log("Dumping future log events to console!", LOG_CRITICAL)
                log(msg, level)
                

def rand():
    result = instance_random.random()
    return result

def hexrep(data, delimit=True):
    try:
        iter(data)
    except TypeError:
        data = [data]
        
    delimiter = ":"
    if not delimit:
        delimiter = ""
    hexrep = delimiter.join("{:02x}".format(c) for c in data)
    return hexrep

def prettyhexrep(data):
    delimiter = ""
    hexrep = "<"+delimiter.join("{:02x}".format(c) for c in data)+">"
    return hexrep

def prettysize(num, suffix='B'):
    units = ['','K','M','G','T','P','E','Z']
    last_unit = 'Y'

    if suffix == 'b':
        num *= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1000.0:
            if unit == "":
                return "%.0f %s%s" % (num, unit, suffix)
            else:
                return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

def prettytime(time, verbose=False):
    days = int(time // (24 * 3600))
    time = time % (24 * 3600)
    hours = int(time // 3600)
    time %= 3600
    minutes = int(time // 60)
    time %= 60
    seconds = round(time, 2)
    
    ss = "" if seconds == 1 else "s"
    sm = "" if minutes == 1 else "s"
    sh = "" if hours == 1 else "s"
    sd = "" if days == 1 else "s"

    components = []
    if days > 0:
        components.append(str(days)+" day"+sd if verbose else str(days)+"d")

    if hours > 0:
        components.append(str(hours)+" hour"+sh if verbose else str(hours)+"h")

    if minutes > 0:
        components.append(str(minutes)+" minute"+sm if verbose else str(minutes)+"m")

    if seconds > 0:
        components.append(str(seconds)+" second"+ss if verbose else str(seconds)+"s")

    i = 0
    tstr = ""
    for c in components:
        i += 1
        if i == 1:
            pass
        elif i < len(components):
            tstr += ", "
        elif i == len(components):
            tstr += " and "

        tstr += c

    if tstr == "":
        return "0s"
    else:
        return tstr

def phyparams():
    print("Required Physical Layer MTU : "+str(Reticulum.MTU)+" bytes")
    print("Plaintext Packet MDU        : "+str(Packet.PLAIN_MDU)+" bytes")
    print("Encrypted Packet MDU        : "+str(Packet.ENCRYPTED_MDU)+" bytes")
    print("Link Curve                  : "+str(Link.CURVE))
    print("Link Packet MDU             : "+str(Packet.ENCRYPTED_MDU)+" bytes")
    print("Link Public Key Size        : "+str(Link.ECPUBSIZE*8)+" bits")
    print("Link Private Key Size       : "+str(Link.KEYSIZE*8)+" bits")

def panic():
    os._exit(255)

def exit():
    print("")
    sys.exit(0)