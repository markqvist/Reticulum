from Interfaces import *
import ConfigParser
import jsonpickle
from vendor.configobj import ConfigObj
import struct
import array
import os.path
import os

import FPE

class FlexPE:
	MTU          = 500
	router       = None
	config       = None
	destinations = []
	interfaces   = []
	configdir = os.path.expanduser("~")+"/.flexpe"
	configpath   = configdir+"/config"

	packetlist = []

	def __init__(self,config=None):
		if config != None:
			self.configpath = config
		else:
			self.configpath = FlexPE.configpath

		if os.path.isfile(self.configpath):
			self.config = ConfigObj(self.configpath)
			FPE.log("Configuration loaded from "+self.configpath)
		else:
			FPE.log("Could not load config file, creating default configuration...")
			self.createDefaultConfig()

		self.applyConfig()
		FlexPE.router = self

	@staticmethod
	def addDestination(destination):
		destination.MTU = FlexPE.MTU
		FlexPE.destinations.append(destination)

	@staticmethod
	def incoming(data):
		packet_hash = FPE.Identity.fullHash(data)

		if not packet_hash in FlexPE.packetlist:
			FlexPE.packetlist.append(packet_hash)
			packet = FPE.Packet(None, data)
			packet.unpack()

			if packet.packet_type == FPE.Packet.ANNOUNCE:
				FPE.Identity.validateAnnounce(packet)
			
			if packet.packet_type == FPE.Packet.RESOURCE:
				for destination in FlexPE.destinations:
					if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
						destination.receive(packet.data)

	@staticmethod
	def outbound(raw):
		for interface in FlexPE.interfaces:
			if interface.OUT:
				FPE.log("Transmitting via: "+str(interface), FPE.LOG_DEBUG)
				interface.processOutgoing(raw)

	def applyConfig(self):
		for option in self.config["logging"]:
			value = self.config["logging"][option]
			if option == "loglevel":
				FPE.loglevel = int(value)

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