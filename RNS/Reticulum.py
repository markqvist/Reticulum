from Interfaces import *
import ConfigParser
from vendor.configobj import ConfigObj
import atexit
import struct
import array
import os.path
import os
import RNS

import traceback

class Reticulum:
	MTU          = 500
	router       = None
	config       = None
	
	configdir    = os.path.expanduser("~")+"/.reticulum"
	configpath   = ""
	storagepath  = ""
	cachepath    = ""
	
	def __init__(self,configdir=None):
		if configdir != None:
			Reticulum.configdir = configdir
		
		Reticulum.configpath   = Reticulum.configdir+"/config"
		Reticulum.storagepath = Reticulum.configdir+"/storage"
		Reticulum.cachepath = Reticulum.configdir+"/storage/cache"

		if not os.path.isdir(Reticulum.storagepath):
			os.makedirs(Reticulum.storagepath)

		if not os.path.isdir(Reticulum.cachepath):
			os.makedirs(Reticulum.cachepath)

		if os.path.isfile(self.configpath):
			self.config = ConfigObj(self.configpath)
			RNS.log("Configuration loaded from "+self.configpath)
		else:
			RNS.log("Could not load config file, creating default configuration...")
			self.createDefaultConfig()
			RNS.log("Default config file created. Make any necessary changes in "+Reticulum.configdir+"/config and start Reticulum again.")
			RNS.log("Exiting now!")
			exit(1)

		self.applyConfig()
		RNS.Identity.loadKnownDestinations()
		Reticulum.router = self

		atexit.register(RNS.Identity.exitHandler)

	def applyConfig(self):
		if "logging" in self.config:
			for option in self.config["logging"]:
				value = self.config["logging"][option]
				if option == "loglevel":
					RNS.loglevel = int(value)

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
						slottime
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
						spreadingfactor						
					)

					if "outgoing" in c and c["outgoing"].lower() == "true":
						interface.OUT = True
					else:
						interface.OUT = False

					RNS.Transport.interfaces.append(interface)

			except Exception as e:
				RNS.log("The interface \""+name+"\" could not be created. Check your configuration file for errors!", RNS.LOG_ERROR)
				RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
				#traceback.print_exc()
				



	def createDefaultConfig(self):
		self.config = ConfigObj()
		self.config.filename = Reticulum.configpath
		self.config["interfaces"] = {}
		self.config["interfaces"]["Default UDP Interface"] = {}
		self.config["interfaces"]["Default UDP Interface"]["type"] = "UdpInterface"
		self.config["interfaces"]["Default UDP Interface"]["listen_ip"] = "0.0.0.0"
		self.config["interfaces"]["Default UDP Interface"]["listen_port"] = 7777
		self.config["interfaces"]["Default UDP Interface"]["forward_ip"] = "255.255.255.255"
		self.config["interfaces"]["Default UDP Interface"]["forward_port"] = 7777
		self.config["interfaces"]["Default UDP Interface"]["use_as_outgoing"] = "true"
		if not os.path.isdir(Reticulum.configdir):
			os.makedirs(Reticulum.configdir)
		self.config.write()
		self.applyConfig()