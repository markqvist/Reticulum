import os
import sys
import glob
import time
import random

from .Reticulum import Reticulum
from .Identity import Identity
from .Link import Link
from .Transport import Transport
from .Destination import Destination
from .Packet import Packet
from .Packet import PacketReceipt
from .Resource import Resource

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

LOG_STDOUT	 = 0x91
LOG_FILE     = 0x92

loglevel 	 = LOG_NOTICE
logfile      = None
logdest      = LOG_STDOUT
logtimefmt   = "%Y-%m-%d %H:%M:%S"

random.seed(os.urandom(10))

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

def log(msg, level=3):
	# TODO: not thread safe
	if loglevel >= level:
		timestamp = time.time()
		logstring = "["+time.strftime(logtimefmt)+"] ["+loglevelname(level)+"] "+msg

		if (logdest == LOG_STDOUT):
			print(logstring)

		if (logdest == LOG_FILE and logfile != None):
			file = open(logfile, "a")
			file.write(logstring+"\n")
			file.close()

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