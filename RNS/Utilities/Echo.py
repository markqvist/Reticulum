import argparse
import time
import RNS

# Let's define an app name. We'll use this for all
# destinations we create. Since this echo example
# is part of a range of example utilities, we'll put
# them all within the app namespace "example_utilities"
APP_NAME = "example_utilitites"

# This initialisation is executed when the users chooses
# to run as a server
def server(configpath):
	# We must first initialise Reticulum
	RNS = RNS.Reticulum(configpath)
	
	# Randomly create a new identity for our echo server
	server_identity = RNS.Identity()

	# We create a destination that clients can query. We want
	# to be able to verify echo replies to our clients, so we
	# create a "single" destination that can receive encrypted
	# messages. This way the client can send a request and be
	# certain that no-one else than this destination was able
	# to read it. 
	echo_destination = RNS.Destination(server_identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "echo", "request")
	
	# Tell the destination which function in our program to
	# run when a packet is received.
	echo_destination.setCallback(serverCallback)

	# Everything's ready!
	# Let's Wait for client requests or user input
	announceLoop(echo_destination)


def announceLoop(destination):
	# Let the user know that everything is ready
	RNS.log("Echo server "+RNS.prettyhexrep(destination.hash)+" running, hit enter to send announce (Ctrl-C to quit)")

	# We enter a loop that runs until the users exits.
	# If the user just hits enter, we will announce our server
	# destination on the network, which will let clients know
	# how to create messages directed towards it.
	while True:
		entered = raw_input()
		destination.announce()
		RNS.log("Sent announce from "+RNS.prettyhexrep(destination.hash))


def serverCallback(message, packet):
	# We have received am echo request from a client! When
	# a client sends a request, it will include the hash of
	# it's identity in the message. Since we know that the
	# client has created a listening destination using this
	# identity hash, we can construct an outgoing destination
	# to direct our response to. The hash is sent in binary
	# format, so we encode it as printable hexadecimal first,
	# since aspect names need to in printable text.
	client_identity_hexhash = message.encode("hex_codec")

	# We can now create a destination that will let us reach
	# the client which send the echo request. 
	reply_destination = RNS.Destination(None, RNS.Destination.OUT, RNS.Destination.PLAIN, APP_NAME, "echo", "reply", client_identity_hexhash)

	# Let's encode the reply destination hash in a readable
	# way, so we can output some info to the user.
	reply_destination_hexhash = reply_destination.hash.encode("hex_codec")

	# Tell the user that we received an echo request, and
	# that we are going to send a reply to the requester.
	RNS.log("Received packet from <"+reply_destination_hexhash+">, sending reply")

	# To let the client know that we got the echo request,
	# we will use the "proof" functions of Reticulum. In most
	# applications, the proving of packets will occur fully
	# automatically, but in some cases like this, it can be
	# beneficial to use the functions manually, since it
	# neatly provides functionality that can unequivocally
	# prove the receipt of the request to the client.
	#
	# Using the proof functionality is very simple, we just
	# need to call the "prove" method on the packet we wish
	# to prove, and specify which destination it should be
	# directed to.
	packet.prove(reply_destination)


# We need a global list to hold sent echo requests
sent_requests = []
# This initialisation is executed when the users chooses
# to run as a client
def client(destination_hexhash, configpath):
	# We need a binary representation of the destination
	# hash that was entered on the command line
	try:
		if len(destination_hexhash) != 20:
			raise ValueError("Destination length is invalid, must be 20 hexadecimal characters (10 bytes)")
		destination_hash = destination_hexhash.decode("hex")
	except:
		RNS.log("Invalid destination entered. Check your input!")
		exit()

	# We must first initialise Reticulum
	RNS = RNS.Reticulum(configpath)

	# Randomly create a new identity for our echo server
	client_identity = RNS.Identity()

	# Let's set up a destination for replies to our echo
	# requests. This destination will be used by the server
	# to direct replies to. We're going to use a "plain"
	# destination, so the server can send replies back
	# without knowing any public keys of the client. In this
	# case, such a design is benificial, since any client
	# can send echo requests directly to the server, without
	# first having to announce it's destination, or include
	# public keys in the echo request
	#
	# We will use the destination naming convention of:
	# example_utilities.echo.reply.<IDENTITY_HASH>
	# where the last part is a hex representation of the hash
	# of our "client_identity". We need to include this to
	# create a unique destination for the server to respond to.
	# If we had used a "single" destination, something equivalent
	# to this process would have happened automatically.
	reply_destination = RNS.Destination(client_identity, RNS.Destination.IN, RNS.Destination.PLAIN, APP_NAME, "echo", "reply", client_identity.hexhash)

	# Since we are only expecting packets of the "proof"
	# type to reach our reply destination, we just set the
	# proof callback (and in this case not the normal
	# message callback)
	reply_destination.setProofCallback(clientProofCallback)

	# Tell the user that the client is ready!
	RNS.log("Echo client "+RNS.prettyhexrep(reply_destination.hash)+" ready, hit enter to send echo request (Ctrl-C to quit)")

	# We enter a loop that runs until the user exits.
	# If the user hits enter, we will try to send an
	# echo request to the destination specified on the
	# command line.
	while True:
		raw_input()
		# To address the server, we need to know it's public
		# key, so we check if Reticulum knows this destination.
		# This is done by calling the "recall" method of the
		# Identity module. If the destination is known, it will
		# return an Identity instance that can be used in
		# outgoing destinations.
		server_identity = RNS.Identity.recall(destination_hash)
		if server_identity != None:
			# We got the correct identity instance from the
			# recall method, so let's create an outgoing
			# destination. We use the naming convention:
			# example_utilities.echo.request
			# Since this is a "single" destination, the identity
			# hash will be automatically added to the end of
			# the name.
			request_destination = RNS.Destination(server_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "echo", "request")

			# The destination is ready, so let's create a packet.
			# We set the destination to the request_destination
			# that was just created, and the only data we add
			# is the identity hash of our client identity.
			# Including that information will let the server
			# create a destination to send replies to.
			echo_request = RNS.Packet(request_destination, client_identity.hash)

			# Send the packet!
			echo_request.send()

			# Add the request to our list of sent packets
			sent_requests.append(echo_request)

			# Tell the user that the echo request was sent
			RNS.log("Sent echo request to "+RNS.prettyhexrep(request_destination.hash))
		else:
			# If we do not know this destination, tell the
			# user to wait for an announce to arrive.
			RNS.log("Destination is not yet known. Wait for an announce to arrive.")

# This method is called when our reply destination
# receives a proof packet.
def clientProofCallback(proof_packet):
	# We save the current time so we can calculate
	# round-trip time for the packet
	now = time.time()

	# Let's look through our list of sent requests,
	# and see if we can find one that matches the
	# proof we just received.
	for unproven_packet in sent_requests:
		try:
			# Check that the proof hash matches the
			# hash of the packet we sent earlier
			if unproven_packet.packet_hash == proof_packet.data[:32]:
				# We need to actually calidate the proof.
				# This is simply done by calling the
				# validateProofPacket method on the packet
				# we sent earlier.
				if unproven_packet.validateProofPacket(proof_packet):
					# If the proof is valid, we will calculate
					# the round-trip time, and inform the user.
					rtt = now - unproven_packet.sent_at
					if (rtt >= 1):
						rtt = round(rtt, 3)
						rttstring = str(rtt)+" seconds"
					else:
						rtt = round(rtt*1000, 3)
						rttstring = str(rtt)+" milliseconds"
					
					RNS.log(
						"Valid echo reply, proved by "+RNS.prettyhexrep(unproven_packet.destination.hash)+
						", round-trip time was "+rttstring
						)
					# Perform some cleanup
					sent_requests.remove(unproven_packet)
					del unproven_packet
				else:
					# If the proof was invalid, we inform 
					# the user of this.
					RNS.log("Echo reply received, but proof was invalid")
		except:
			RNS.log("Proof packet received, but packet contained invalid or unparsable data")



if __name__ == "__main__":
	# Set up command line arguments and start
	# the selected program mode.
	try:
		parser = argparse.ArgumentParser(description="Simple echo server and client utility")
		parser.add_argument("-s", "--server", action="store_true", help="wait for incoming packets from clients")
		parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
		parser.add_argument("destination", nargs="?", default=None, help="hexadecimal hash of the server destination", type=str)
		args = parser.parse_args()

		if args.server:
			configarg=None
			if args.config:
				configarg = args.config
			server(configarg)
		else:
			configarg=None
			if args.config:
				configarg = args.config
			client(args.destination, configarg)
	except KeyboardInterrupt:
		exit()