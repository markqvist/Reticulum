from Interfaces import *
import ConfigParser
import jsonpickle
from vendor.configobj import ConfigObj
import struct
import array
import os.path
import os

class FlexPE:
	MTU          = 700
	router       = None
	config       = None
	destinations = []
	interfaces   = []
	configdir = os.path.expanduser("~")+"/.flexpe"
	configpath   = configdir+"/config"


	def __init__(self):
		if os.path.isfile(FlexPE.configpath):
			self.config = ConfigObj(FlexPE.configpath)
		else:
			print("Could not load config file, creating default configuration...")
			self.createDefaultConfig()

		self.applyConfig()
		print FlexPE.interfaces

		FlexPE.router = self

	@staticmethod
	def addDestination(destination):
		destination.MTU = FlexPE.MTU
		FlexPE.destinations.append(destination)

	@staticmethod
	def incoming(data):
		
		header = struct.unpack("B", data[0])

		hash = data[1:11]
		type = header[0] & 0x03

		for destination in FlexPE.destinations:
			if destination.hash == hash and destination.type == type:
				destination.receive(data[11:])

	@staticmethod
	def outbound(raw):
		for interface in FlexPE.interfaces:
			if interface.OUT:
				interface.processOutgoing(raw)

	def applyConfig(self):
		for name in self.config["interfaces"]:
			c = self.config["interfaces"][name]
			try:
				if c["type"] == "UdpInterface":
					interface = UdpInterface.UdpInterface(
						self,
						c["listen_ip"],
						int(c["listen_port"]),
						c["forward_ip"],
						int(c["forward_port"])
					)

					if c["use_as_outgoing"].lower() == "true":
						interface.OUT = True

					interface.name = name
					FlexPE.interfaces.append(interface)

				if c["type"] == "SerialInterface":
					interface = SerialInterface.SerialInterface(
						self,
						c["port"],
						int(c["speed"]),
						int(c["databits"]),
						c["parity"],
						int(c["stopbits"])
					)

					if c["use_as_outgoing"].lower() == "true":
						interface.OUT = True

					interface.name = name
					FlexPE.interfaces.append(interface)

			except Exception as e:
				print("The interface \""+name+"\" could not be created. Check your configuration file for errors!")
				print("The contained error was: "+str(e))
				



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