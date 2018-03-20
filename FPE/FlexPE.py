from Interfaces import *
import ConfigParser
from vendor.configobj import ConfigObj
import atexit
import struct
import array
import os.path
import os

import FPE

class FlexPE:
	MTU          = 500
	router       = None
	config       = None
	
	configdir    = os.path.expanduser("~")+"/.flexpe"
	configpath   = ""
	storagepath  = ""
	cachepath    = ""
	
	def __init__(self,configdir=None):
		if configdir != None:
			FlexPE.configdir = configdir
		
		FlexPE.configpath   = FlexPE.configdir+"/config"
		FlexPE.storagepath = FlexPE.configdir+"/storage"
		FlexPE.cachepath = FlexPE.configdir+"/storage/cache"

		if not os.path.isdir(FlexPE.storagepath):
			os.makedirs(FlexPE.storagepath)

		if not os.path.isdir(FlexPE.cachepath):
			os.makedirs(FlexPE.cachepath)

		if os.path.isfile(self.configpath):
			self.config = ConfigObj(self.configpath)
			FPE.log("Configuration loaded from "+self.configpath)
		else:
			FPE.log("Could not load config file, creating default configuration...")
			self.createDefaultConfig()

		self.applyConfig()
		FPE.Identity.loadKnownDestinations()
		FlexPE.router = self

		atexit.register(FPE.Identity.exitHandler)

	def applyConfig(self):
		if "logging" in self.config:
			for option in self.config["logging"]:
				value = self.config["logging"][option]
				if option == "loglevel":
					FPE.loglevel = int(value)

		for name in self.config["interfaces"]:
			c = self.config["interfaces"][name]
			try:
				if c["type"] == "UdpInterface":
					interface = UdpInterface.UdpInterface(
						FPE.Transport,
						c["listen_ip"],
						int(c["listen_port"]),
						c["forward_ip"],
						int(c["forward_port"])
					)

					if c["use_as_outgoing"].lower() == "true":
						interface.OUT = True

					interface.name = name
					FPE.Transport.interfaces.append(interface)

				if c["type"] == "SerialInterface":
					interface = SerialInterface.SerialInterface(
						FPE.Transport,
						c["port"],
						int(c["speed"]),
						int(c["databits"]),
						c["parity"],
						int(c["stopbits"])
					)

					if c["use_as_outgoing"].lower() == "true":
						interface.OUT = True

					interface.name = name
					FPE.Transport.interfaces.append(interface)

			except Exception as e:
				FPE.log("The interface \""+name+"\" could not be created. Check your configuration file for errors!", FPE.LOG_ERROR)
				FPE.log("The contained exception was: "+str(e), FPE.LOG_ERROR)
				



	def createDefaultConfig(self):
		self.config = ConfigObj()
		self.config.filename = FlexPE.configpath
		self.config["interfaces"] = {}
		self.config["interfaces"]["Default UDP Interface"] = {}
		self.config["interfaces"]["Default UDP Interface"]["type"] = "UdpInterface"
		self.config["interfaces"]["Default UDP Interface"]["listen_ip"] = "0.0.0.0"
		self.config["interfaces"]["Default UDP Interface"]["listen_port"] = 7777
		self.config["interfaces"]["Default UDP Interface"]["forward_ip"] = "255.255.255.255"
		self.config["interfaces"]["Default UDP Interface"]["forward_port"] = 7777
		self.config["interfaces"]["Default UDP Interface"]["use_as_outgoing"] = "true"
		if not os.path.isdir(FlexPE.configdir):
			os.makedirs(FlexPE.configdir)
		self.config.write()
		self.applyConfig()