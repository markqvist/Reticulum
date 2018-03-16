from FlexPE import FlexPE

class Transport:
	@staticmethod
	def outbound(raw):
		FlexPE.outbound(raw)

	@staticmethod
	def registerDestination(destination):
		FlexPE.addDestination(destination)