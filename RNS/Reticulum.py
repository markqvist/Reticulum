from .Interfaces import *
import configparser
from .vendor.configobj import ConfigObj
import RNS
import atexit
import struct
import array
import os.path
import os
import RNS

#import traceback

class Reticulum:
	MTU            = 500
	HEADER_MAXSIZE = 23

	PAD_AES_HMAC   = 64
	MDU            = MTU - HEADER_MAXSIZE
	LINK_MDU       = MDU - PAD_AES_HMAC
	router         = None
	config         = None
	
	configdir    = os.path.expanduser("~")+"/.reticulum"
	configpath   = ""
	storagepath  = ""
	cachepath    = ""
	
	@staticmethod
	def exit_handler():
		RNS.Transport.exitHandler()
		RNS.Identity.exitHandler()

	def __init__(self,configdir=None):
		if configdir != None:
			Reticulum.configdir = configdir
		
		Reticulum.configpath   = Reticulum.configdir+"/config"
		Reticulum.storagepath = Reticulum.configdir+"/storage"
		Reticulum.cachepath = Reticulum.configdir+"/storage/cache"

		Reticulum.__allow_unencrypted = False
		Reticulum.__use_implicit_proof = True

		if not os.path.isdir(Reticulum.storagepath):
			os.makedirs(Reticulum.storagepath)

		if not os.path.isdir(Reticulum.cachepath):
			os.makedirs(Reticulum.cachepath)

		if os.path.isfile(self.configpath):
			self.config = ConfigObj(self.configpath)
			RNS.log("Configuration loaded from "+self.configpath)
		else:
			RNS.log("Could not load config file, creating default configuration file...")
			self.createDefaultConfig()
			RNS.log("Default config file created. Make any necessary changes in "+Reticulum.configdir+"/config and start Reticulum again.")
			RNS.log("Exiting now!")
			exit(1)

		self.applyConfig()
		RNS.Identity.loadKnownDestinations()
		Reticulum.router = self

		RNS.Transport.start()

		atexit.register(Reticulum.exit_handler)

	def applyConfig(self):
		if "logging" in self.config:
			for option in self.config["logging"]:
				value = self.config["logging"][option]
				if option == "loglevel":
					RNS.loglevel = int(value)
					if RNS.loglevel < 0:
						RNS.loglevel = 0
					if RNS.loglevel > 7:
						RNS.loglevel = 7

		if "reticulum" in self.config:
			for option in self.config["reticulum"]:
				value = self.config["reticulum"][option]
				if option == "use_implicit_proof":
					if value == "true":
						Reticulum.__use_implicit_proof = True
					if value == "false":
						Reticulum.__use_implicit_proof = False
				if option == "allow_unencrypted":
					if value == "true":
						RNS.log("", RNS.LOG_CRITICAL)
						RNS.log("! ! !", RNS.LOG_CRITICAL)
						RNS.log("", RNS.LOG_CRITICAL)
						RNS.log("Danger! Encryptionless links have been allowed in the config file!", RNS.LOG_CRITICAL)
						RNS.log("Beware of the consequences! Any data sent over a link can potentially be intercepted,", RNS.LOG_CRITICAL)
						RNS.log("read and modified! If you are not absolutely sure that you want this,", RNS.LOG_CRITICAL)
						RNS.log("you should exit Reticulum NOW and change your config file!", RNS.LOG_CRITICAL)
						RNS.log("", RNS.LOG_CRITICAL)
						RNS.log("! ! !", RNS.LOG_CRITICAL)
						RNS.log("", RNS.LOG_CRITICAL)
						Reticulum.__allow_unencrypted = True


		for name in self.config["interfaces"]:
			c = self.config["interfaces"][name]
			try:
				if c["type"] == "UdpInterface":
					interface = UdpInterface.UdpInterface(
						RNS.Transport,
						name,
						c["listen_ip"],
						int(c["listen_port"]),
						c["forward_ip"],
						int(c["forward_port"])
					)

					if "outgoing" in c and c["outgoing"].lower() == "true":
						interface.OUT = True
					else:
						interface.OUT = False

					RNS.Transport.interfaces.append(interface)

				if c["type"] == "SerialInterface":
					port = c["port"] if "port" in c else None
					speed = int(c["speed"]) if "speed" in c else 9600
					databits = int(c["databits"]) if "databits" in c else 8
					parity = c["parity"] if "parity" in c else "N"
					stopbits = int(c["stopbits"]) if "stopbits" in c else 1

					if port == None:
						raise ValueError("No port specified for serial interface")

					interface = SerialInterface.SerialInterface(
						RNS.Transport,
						name,
						port,
						speed,
						databits,
						parity,
						stopbits
					)

					if "outgoing" in c and c["outgoing"].lower() == "true":
						interface.OUT = True
					else:
						interface.OUT = False

					RNS.Transport.interfaces.append(interface)

				if c["type"] == "KISSInterface":
					preamble = int(c["preamble"]) if "preamble" in c else None
					txtail = int(c["txtail"]) if "txtail" in c else None
					persistence = int(c["persistence"]) if "persistence" in c else None
					slottime = int(c["slottime"]) if "slottime" in c else None
					flow_control = (True if c["flow_control"] == "true" else False) if "flow_control" in c else False

					port = c["port"] if "port" in c else None
					speed = int(c["speed"]) if "speed" in c else 9600
					databits = int(c["databits"]) if "databits" in c else 8
					parity = c["parity"] if "parity" in c else "N"
					stopbits = int(c["stopbits"]) if "stopbits" in c else 1

					if port == None:
						raise ValueError("No port specified for serial interface")

					interface = KISSInterface.KISSInterface(
						RNS.Transport,
						name,
						port,
						speed,
						databits,
						parity,
						stopbits,
						preamble,
						txtail,
						persistence,
						slottime,
						flow_control
					)

					if "outgoing" in c and c["outgoing"].lower() == "true":
						interface.OUT = True
					else:
						interface.OUT = False

					RNS.Transport.interfaces.append(interface)

				if c["type"] == "AX25KISSInterface":
					preamble = int(c["preamble"]) if "preamble" in c else None
					txtail = int(c["txtail"]) if "txtail" in c else None
					persistence = int(c["persistence"]) if "persistence" in c else None
					slottime = int(c["slottime"]) if "slottime" in c else None
					flow_control = (True if c["flow_control"] == "true" else False) if "flow_control" in c else False

					port = c["port"] if "port" in c else None
					speed = int(c["speed"]) if "speed" in c else 9600
					databits = int(c["databits"]) if "databits" in c else 8
					parity = c["parity"] if "parity" in c else "N"
					stopbits = int(c["stopbits"]) if "stopbits" in c else 1

					callsign = c["callsign"] if "callsign" in c else ""
					ssid = int(c["ssid"]) if "ssid" in c else -1

					if port == None:
						raise ValueError("No port specified for serial interface")

					interface = AX25KISSInterface.AX25KISSInterface(
						RNS.Transport,
						name,
						callsign,
						ssid,
						port,
						speed,
						databits,
						parity,
						stopbits,
						preamble,
						txtail,
						persistence,
						slottime,
						flow_control
					)

					if "outgoing" in c and c["outgoing"].lower() == "true":
						interface.OUT = True
					else:
						interface.OUT = False

					RNS.Transport.interfaces.append(interface)

				if c["type"] == "RNodeInterface":
					frequency = int(c["frequency"]) if "frequency" in c else None
					bandwidth = int(c["bandwidth"]) if "bandwidth" in c else None
					txpower = int(c["txpower"]) if "txpower" in c else None
					spreadingfactor = int(c["spreadingfactor"]) if "spreadingfactor" in c else None
					flow_control = (True if c["flow_control"] == "true" else False) if "flow_control" in c else False

					port = c["port"] if "port" in c else None
					
					if port == None:
						raise ValueError("No port specified for RNode interface")

					interface = RNodeInterface.RNodeInterface(
						RNS.Transport,
						name,
						port,
						frequency,
						bandwidth,
						txpower,
						spreadingfactor,
						flow_control
					)

					if "outgoing" in c and c["outgoing"].lower() == "true":
						interface.OUT = True
					else:
						interface.OUT = False

					RNS.Transport.interfaces.append(interface)

			except Exception as e:
				RNS.log("The interface \""+name+"\" could not be created. Check your configuration file for errors!", RNS.LOG_ERROR)
				RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
				raise e
				

	def createDefaultConfig(self):
		self.config = ConfigObj()
		self.config.filename = Reticulum.configpath
		self.config["reticulum"] = {}
		self.config["reticulum"]["allow_unencrypted"] = False
		self.config["logging"] = {}
		self.config["logging"]["loglevel"] = 4
		self.config["interfaces"] = {}
		self.config["interfaces"]["Default UDP Interface"] = {}
		self.config["interfaces"]["Default UDP Interface"]["type"] = "UdpInterface"
		self.config["interfaces"]["Default UDP Interface"]["listen_ip"] = "0.0.0.0"
		self.config["interfaces"]["Default UDP Interface"]["listen_port"] = 7777
		self.config["interfaces"]["Default UDP Interface"]["forward_ip"] = "255.255.255.255"
		self.config["interfaces"]["Default UDP Interface"]["forward_port"] = 7777
		self.config["interfaces"]["Default UDP Interface"]["outgoing"] = "true"
		if not os.path.isdir(Reticulum.configdir):
			os.makedirs(Reticulum.configdir)
		self.config.write()
		self.applyConfig()

	@staticmethod
	def should_allow_unencrypted():
		return Reticulum.__allow_unencrypted

	@staticmethod
	def should_use_implicit_proof():
		return Reticulum.__use_implicit_proof