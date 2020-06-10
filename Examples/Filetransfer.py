##########################################################
# This RNS example demonstrates a simple filetransfer    #
# server and client program. The server will serve a     #
# directory of files, and the clients can list and       #
# download files from the server.                        #
#                                                        #
# Please note that using RNS Resources for large file    #
# transfers is not recommended, since compression,       #
# encryption and hashmap sequencing can take a long time #
# on systems with slow CPUs, which will probably result  #
# in the client timing out before the resource sender    #
# can complete preparing the resource.                   #
#                                                        #
# If you need to transfer large files, use the Bundle    #
# class instead, which will automatically slice the data #
# into chunks suitable for packing as a Resource.        #
##########################################################

import os
import sys
import time
import threading
import argparse
import RNS
import RNS.vendor.umsgpack as umsgpack

# Let's define an app name. We'll use this for all
# destinations we create. Since this echo example
# is part of a range of example utilities, we'll put
# them all within the app namespace "example_utilities"
APP_NAME = "example_utilitites"

# We'll also define a default timeout, in seconds
APP_TIMEOUT = 45.0

##########################################################
#### Server Part #########################################
##########################################################

serve_path = None

# This initialisation is executed when the users chooses
# to run as a server
def server(configpath, path):
	# We must first initialise Reticulum
	reticulum = RNS.Reticulum(configpath)
	
	# Randomly create a new identity for our file server
	server_identity = RNS.Identity()

	global serve_path
	serve_path = path

	# We create a destination that clients can connect to. We
	# want clients to create links to this destination, so we
	# need to create a "single" destination type.
	server_destination = RNS.Destination(server_identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "filetransfer", "server")

	# We configure a function that will get called every time
	# a new client creates a link to this destination.
	server_destination.link_established_callback(client_connected)

	# Everything's ready!
	# Let's Wait for client requests or user input
	announceLoop(server_destination)

def announceLoop(destination):
	# Let the user know that everything is ready
	RNS.log("File server "+RNS.prettyhexrep(destination.hash)+" running")
	RNS.log("Hit enter to manually send an announce (Ctrl-C to quit)")

	# We enter a loop that runs until the users exits.
	# If the user hits enter, we will announce our server
	# destination on the network, which will let clients
	# know how to create messages directed towards it.
	while True:
		entered = input()
		destination.announce()
		RNS.log("Sent announce from "+RNS.prettyhexrep(destination.hash))

# Here's a convenience function for listing all files
# in our served directory
def list_files():
	# We add all entries from the directory that are
	# actual files, and does not start with "."
	global serve_path
	return [file for file in os.listdir(serve_path) if os.path.isfile(os.path.join(serve_path, file)) and file[:1] != "."]

# When a client establishes a link to our server
# destination, this function will be called with
# a reference to the link. We then send the client
# a list of files hosted on the server.
def client_connected(link):
	# Check if the served directory still exists
	if os.path.isdir(serve_path):
		RNS.log("Client connected, sending file list...")

		link.link_closed_callback(client_disconnected)

		# We pack a list of files for sending in a packet
		data = umsgpack.packb(list_files())

		# Check the size of the packed data
		if len(data) <= RNS.Link.MDU:
			# If it fits in one packet, we will just
			# send it as a single packet over the link.
			list_packet = RNS.Packet(link, data)
			list_receipt = list_packet.send()
			list_receipt.set_timeout(APP_TIMEOUT)
			list_receipt.delivery_callback(list_delivered)
			list_receipt.timeout_callback(list_timeout)
		else:
			RNS.log("Too many files in served directory!", RNS.LOG_ERROR)
			RNS.log("You should implement a function to split the filelist over multiple packets.", RNS.LOG_ERROR)
			RNS.log("Hint: The client already supports it :)", RNS.LOG_ERROR)
			
		# After this, we're just going to keep the link
		# open until the client requests a file. We'll
		# configure a function that get's called when
		# the client sends a packet with a file request.
		link.packet_callback(client_request)
	else:
		RNS.log("Client connected, but served path no longer exists!", RNS.LOG_ERROR)
		link.teardown()

def client_disconnected(link):
	RNS.log("Client disconnected")

def client_request(message, packet):
	global serve_path
	filename = message.decode("utf-8")
	if filename in list_files():
		try:
			# If we have the requested file, we'll
			# read it and pack it as a resource
			RNS.log("Client requested \""+filename+"\"")
			file = open(os.path.join(serve_path, filename), "rb")
			file_data = file.read()
			file.close()

			file_resource = RNS.Resource(file_data, packet.link, callback=resource_sending_concluded)
			file_resource.filename = filename
		except:
			# If somethign went wrong, we close
			# the link
			RNS.log("Error while reading file \""+filename+"\"", RNS.LOG_ERROR)
			packet.link.teardown()
	else:
		# If we don't have it, we close the link
		RNS.log("Client requested an unknown file")
		packet.link.teardown()

# This function is called on the server when a
# resource transfer concludes.
def resource_sending_concluded(resource):
	if hasattr(resource, "filename"):
		name = resource.filename
	else:
		name = "resource"

	if resource.status == RNS.Resource.COMPLETE:
		RNS.log("Done sending \""+name+"\" to client")
	elif resource.status == RNS.Resource.FAILED:
		RNS.log("Sending \""+name+"\" to client failed")

def list_delivered(receipt):
	RNS.log("The file list was received by the client")

def list_timeout(receipt):
	RNS.log("Sending list to client timed out, closing this link")
	link = receipt.destination
	link.teardown()

##########################################################
#### Client Part #########################################
##########################################################

# We store a global list of files available on the server
server_files = []

# A reference to the server link
server_link = None

# And a reference to the current download
current_download = None
current_filename = None

# This initialisation is executed when the users chooses
# to run as a client
def client(destination_hexhash, configpath):
	# We need a binary representation of the destination
	# hash that was entered on the command line
	try:
		if len(destination_hexhash) != 20:
			raise ValueError("Destination length is invalid, must be 20 hexadecimal characters (10 bytes)")
		destination_hash = bytes.fromhex(destination_hexhash)
	except:
		RNS.log("Invalid destination entered. Check your input!\n")
		exit()

	# We must first initialise Reticulum
	reticulum = RNS.Reticulum(configpath)


	# Check if we know a path to the destination
	if not RNS.Transport.hasPath(destination_hash):
		RNS.log("Destination is not yet known. Requesting path and waiting for announce to arrive...")
		RNS.Transport.requestPath(destination_hash)
		while not RNS.Transport.hasPath(destination_hash):
			time.sleep(0.1)

	# Recall the server identity
	server_identity = RNS.Identity.recall(destination_hash)

	# Inform the user that we'll begin connecting
	RNS.log("Establishing link with server...")

	# When the server identity is known, we set
	# up a destination
	server_destination = RNS.Destination(server_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "filetransfer", "server")

	# We also want to automatically prove incoming packets
	server_destination.set_proof_strategy(RNS.Destination.PROVE_ALL)

	# And create a link
	link = RNS.Link(server_destination)

	# We expect any normal data packets on the link
	# to contain a list of served files, so we set
	# a callback accordingly
	link.packet_callback(filelist_received)

	# We'll also set up functions to inform the
	# user when the link is established or closed
	link.link_established_callback(link_established)
	link.link_closed_callback(link_closed)

	# And set the link to automatically begin
	# downloading advertised resources
	link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
	link.resource_started_callback(download_began)
	link.resource_concluded_callback(download_concluded)

	menu()

# Requests the specified file from the server
def download(filename):
	global server_link, menu_mode, current_filename
	current_filename = filename

	# We just create a packet containing the
	# requested filename, and send it down the
	# link. We also specify we don't need a
	# packet receipt.
	request_packet = RNS.Packet(server_link, filename.encode("utf-8"), create_receipt=False)
	request_packet.send()
	
	print("")
	print(("Requested \""+filename+"\" from server, waiting for download to begin..."))
	menu_mode = "download_started"

# This function runs a simple menu for the user
# to select which files to download, or quit
menu_mode = None
def menu():
	global server_files, server_link
	# Wait until we have a filelist
	while len(server_files) == 0:
		time.sleep(0.1)
	RNS.log("Ready!")
	time.sleep(0.5)

	global menu_mode
	menu_mode = "main"
	should_quit = False
	while (not should_quit):
		print_menu()

		while not menu_mode == "main":
			# Wait
			time.sleep(0.25)

		user_input = input()
		if user_input == "q" or user_input == "quit" or user_input == "exit":
			should_quit = True
			print("")
		else:
			if user_input in server_files:
				download(user_input)
			else:
				try:
					if 0 <= int(user_input) < len(server_files):
						download(server_files[int(user_input)])
				except:
					pass

	if should_quit:
		server_link.teardown()

# Prints out menus or screens for the
# various states of the client program.
# It's simple and quite uninteresting.
# I won't go into detail here. Just
# strings basically.
def print_menu():
	global menu_mode

	if menu_mode == "main":
		clear_screen()
		print_filelist()
		print("")
		print("Select a file to download by entering name or number, or q to quit")
		print(("> "), end=' ')
	elif menu_mode == "download_started":
		download_began = time.time()
		while menu_mode == "download_started":
			time.sleep(0.1)
			if time.time() > download_began+APP_TIMEOUT:
				print("The download timed out")
				time.sleep(1)
				server_link.teardown()

	if menu_mode == "downloading":
		print("Download started")
		print("")
		while menu_mode == "downloading":
			global current_download
			percent = round(current_download.progress() * 100.0, 1)
			print(("\rProgress: "+str(percent)+" %   "), end=' ')
			sys.stdout.flush()
			time.sleep(0.1)

	if menu_mode == "save_error":
		print(("\rProgress: 100.0 %"), end=' ')
		sys.stdout.flush()
		print("")
		print("Could not write downloaded file to disk")
		current_download.status = RNS.Resource.FAILED
		menu_mode = "download_concluded"

	if menu_mode == "download_concluded":
		if current_download.status == RNS.Resource.COMPLETE:
			print(("\rProgress: 100.0 %"), end=' ')
			sys.stdout.flush()
			print("")
			print("The download completed! Press enter to return to the menu.")
			input()

		else:
			print("")
			print("The download failed! Press enter to return to the menu.")
			input()

		current_download = None
		menu_mode = "main"
		print_menu()

# This function prints out a list of files
# on the connected server.
def print_filelist():
	global server_files
	print("Files on server:")
	for index,file in enumerate(server_files):
		print("\t("+str(index)+")\t"+file)

def filelist_received(filelist_data, packet):
	global server_files, menu_mode
	try:
		# Unpack the list and extend our
		# local list of available files
		filelist = umsgpack.unpackb(filelist_data)
		for file in filelist:
			if not file in server_files:
				server_files.append(file)

		# If the menu is already visible,
		# we'll update it with what was
		# just received
		if menu_mode == "main":
			print_menu()
	except:
		RNS.log("Invalid file list data received, closing link")
		packet.link.teardown()

# This function is called when a link
# has been established with the server
def link_established(link):
	# We store a reference to the link
	# instance for later use
	global server_link
	server_link = link

	# Inform the user that the server is
	# connected
	RNS.log("Link established with server")
	RNS.log("Waiting for filelist...")

	# And set up a small job to check for
	# a potential timeout in receiving the
	# file list
	thread = threading.Thread(target=filelist_timeout_job)
	thread.setDaemon(True)
	thread.start()

# This job just sleeps for the specified
# time, and then checks if the file list
# was received. If not, the program will
# exit.
def filelist_timeout_job():
	time.sleep(APP_TIMEOUT)

	global server_files
	if len(server_files) == 0:
		RNS.log("Timed out waiting for filelist, exiting")
		os._exit(0)


# When a link is closed, we'll inform the
# user, and exit the program
def link_closed(link):
	if link.teardown_reason == RNS.Link.TIMEOUT:
		RNS.log("The link timed out, exiting now")
	elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
		RNS.log("The link was closed by the server, exiting now")
	else:
		RNS.log("Link closed, exiting now")
	
	RNS.Reticulum.exit_handler()
	time.sleep(1.5)
	os._exit(0)

# When RNS detects that the download has
# started, we'll update our menu state
# so the user can be shown a progress of
# the download.
def download_began(resource):
	global menu_mode, current_download
	current_download = resource
	menu_mode = "downloading"

# When the download concludes, successfully
# or not, we'll update our menu state and 
# inform the user about how it all went.
def download_concluded(resource):
	global menu_mode, current_filename
	saved_filename = current_filename

	if resource.status == RNS.Resource.COMPLETE:
		counter = 0
		while os.path.isfile(saved_filename):
			counter += 1
			saved_filename = current_filename+"."+str(counter)

		try:
			file = open(saved_filename, "wb")
			file.write(resource.data)
			file.close()
			menu_mode = "download_concluded"
		except:
			menu_mode = "save_error"
	else:
		menu_mode = "download_concluded"


# A convenience function for clearing the screen
def clear_screen():
    os.system('cls' if os.name=='nt' else 'clear')

##########################################################
#### Program Startup #####################################
##########################################################

# This part of the program runs at startup,
# and parses input of from the user, and then
# starts up the desired program mode.
if __name__ == "__main__":
	try:
		parser = argparse.ArgumentParser(description="Simple file transfer server and client utility")
		parser.add_argument("-s", "--serve", action="store", metavar="dir", help="serve a directory of files to clients")
		parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
		parser.add_argument("destination", nargs="?", default=None, help="hexadecimal hash of the server destination", type=str)
		args = parser.parse_args()

		if args.config:
			configarg = args.config
		else:
			configarg = None

		if args.serve:
			if os.path.isdir(args.serve):
				server(configarg, args.serve)
			else:
				RNS.log("The specified directory does not exist")
		else:
			if (args.destination == None):
				print("")
				parser.print_help()
				print("")
			else:
				client(args.destination, configarg)

	except KeyboardInterrupt:
		print("")
		exit()