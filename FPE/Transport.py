import FPE

class Transport:
	# Constants
	BROADCAST    = 0x00;
	TRANSPORT    = 0x01;
	RELAY        = 0x02;
	TUNNEL       = 0x03;
	types        = [BROADCAST, TRANSPORT, RELAY, TUNNEL]

	@staticmethod
	def outbound(raw):
		FPE.FlexPE.outbound(raw)

	@staticmethod
	def registerDestination(destination):
		FPE.FlexPE.addDestination(destination)