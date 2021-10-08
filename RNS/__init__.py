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

loglevel     = LOG_NOTICE
logfile      = None
logdest      = LOG_STDOUT
logtimefmt   = "%Y-%m-%d %H:%M:%S"

random.seed(os.urandom(10))

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

def log(msg, level=3, _override_destination = False):
    global _always_override_destination
    
    if loglevel >= level:
        timestamp = time.time()
        logstring = "["+time.strftime(logtimefmt)+"] ["+loglevelname(level)+"] "+msg
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
    result = random.random()
    return result

def hexrep(data, delimit=True):
    delimiter = ":"
    if not delimit:
        delimiter = ""
    hexrep = delimiter.join("{:02x}".format(c) for c in data)
    return hexrep

def prettyhexrep(data):
    delimiter = ""
    hexrep = "<"+delimiter.join("{:02x}".format(c) for c in data)+">"
    return hexrep

def panic():
    os._exit(255)

def exit():
    sys.exit(0)