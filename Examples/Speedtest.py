##########################################################
# This RNS example demonstrates a simple speedtest       #
# program to measure link throughput.                    #
##########################################################

import os
import sys
import time
import argparse
import RNS

# Let's define an app name. We'll use this for all
# destinations we create.
APP_NAME = "example_utilities"

##########################################################
#### Server Part #########################################
##########################################################

latest_client_link = None
first_packet_at = None
last_packet_at = None
received_data = 0
rc = 0
data_cap = 2*1024*1024
printed = False

# This initialisation is executed when the users chooses
# to run as a server
def server(configpath):
    # We must first initialise Reticulum
    reticulum = RNS.Reticulum(configpath)
    
    # Randomly create a new identity for our link example
    server_identity = RNS.Identity()

    # We create a destination that clients can connect to. We
    # want clients to create links to this destination, so we
    # need to create a "single" destination type.
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        APP_NAME,
        "speedtest"
    )

    # We configure a function that will get called every time
    # a new client creates a link to this destination.
    server_destination.set_link_established_callback(client_connected)

    # Everything's ready!
    # Let's Wait for client requests or user input
    server_loop(server_destination)

def server_loop(destination):
    # Let the user know that everything is ready
    RNS.log(
        "Speedtest "+
        RNS.prettyhexrep(destination.hash)+
        " running, waiting for a connection."
    )

    RNS.log("Hit enter to manually send an announce (Ctrl-C to quit)")

    # We enter a loop that runs until the users exits.
    # If the user hits enter, we will announce our server
    # destination on the network, which will let clients
    # know how to create messages directed towards it.
    while True:
        entered = input()
        destination.announce()
        RNS.log("Sent announce from "+RNS.prettyhexrep(destination.hash))

# When a client establishes a link to our server
# destination, this function will be called with
# a reference to the link.
def client_connected(link):
    global latest_client_link, first_packet_at, rc

    RNS.log("Client connected")
    first_packet_at = time.time()
    rc = 0
    link.set_link_closed_callback(client_disconnected)
    link.set_packet_callback(server_packet_received)
    latest_client_link = link

def client_disconnected(link):
    RNS.log("Client disconnected")


# A convenience function for printing a human-
# readable file size
def size_str(num, suffix='B'):
    units = ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']
    last_unit = 'Yi'

    if suffix == 'b':
        num *= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1024.0:
            return "%3.2f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.2f %s%s" % (num, last_unit, suffix)


def server_packet_received(message, packet):
    global latest_client_link, first_packet_at, last_packet_at, received_data, rc, data_cap
    
    received_data += len(packet.data)
    
    rc += 1
    if rc >= 50:
        RNS.log(size_str(received_data))
        rc = 0

    if received_data > data_cap:
        rcv_d = received_data
        received_data = 0
        rc = 0

        last_packet_at = time.time()
        
        # Print statistics
        download_time = last_packet_at-first_packet_at
        hours, rem = divmod(download_time, 3600)
        minutes, seconds = divmod(rem, 60)
        timestring = "{:0>2}:{:0>2}:{:05.2f}".format(int(hours),int(minutes),seconds)

        print("")
        print("")
        print("--- Statistics -----")
        print("\tTime taken       : "+timestring)
        print("\tData transferred : "+size_str(rcv_d))
        print("\tTransfer rate    : "+size_str(rcv_d/download_time, suffix='b')+"/s")
        print("")

        sys.stdout.flush()
        latest_client_link.teardown()
        time.sleep(0.2)
        rc = 0
        received_data = 0
        # latest_client_link.teardown()
        # os._exit(0)


##########################################################
#### Client Part #########################################
##########################################################

# A reference to the server link
server_link = None

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
    if not RNS.Transport.has_path(destination_hash):
        RNS.log("Destination is not yet known. Requesting path and waiting for announce to arrive...")
        RNS.Transport.request_path(destination_hash)
        while not RNS.Transport.has_path(destination_hash):
            time.sleep(0.1)

    # Recall the server identity
    server_identity = RNS.Identity.recall(destination_hash)

    # Inform the user that we'll begin connecting
    RNS.log("Establishing link with server...")

    # When the server identity is known, we set
    # up a destination
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        APP_NAME,
        "speedtest"
    )

    # And create a link
    link = RNS.Link(server_destination)

    # We'll also set up functions to inform the
    # user when the link is established or closed
    link.set_link_established_callback(link_established)
    link.set_link_closed_callback(link_closed)

    # Everything is set up, so let's enter a loop
    # for the user to interact with the example
    client_loop()

def client_loop():
    global server_link

    # Wait for the link to become active
    while not server_link:
        time.sleep(0.1)

    should_quit = False
    while not should_quit:
        try:
            text = input()

            # Check if we should quit the example
            if text == "quit" or text == "q" or text == "exit":
                should_quit = True
                server_link.teardown()

        except Exception as e:
            raise e

# This function is called when a link
# has been established with the server
def link_established(link):
    # We store a reference to the link
    # instance for later use
    global server_link, data_cap, printed
    server_link = link
    data_sent = 0

    # Inform the user that the server is
    # connected
    RNS.log("Link established with server,sending...")
    rd = os.urandom(RNS.Link.MDU)
    started = time.time()
    while link.status == RNS.Link.ACTIVE and data_sent < data_cap*1.25:
        RNS.Packet(server_link, rd, create_receipt=False).send()
        data_sent += len(rd)

        if data_sent > data_cap and not printed:
            printed = True
            ended = time.time()
            # Print statistics
            download_time = ended-started
            hours, rem = divmod(download_time, 3600)
            minutes, seconds = divmod(rem, 60)
            timestring = "{:0>2}:{:0>2}:{:05.2f}".format(int(hours),int(minutes),seconds)
            print("")
            print("")
            print("--- Statistics -----")
            print("\tTime taken       : "+timestring)
            print("\tData transferred : "+size_str(data_sent))
            print("\tTransfer rate    : "+size_str(data_sent/download_time, suffix='b')+"/s")
            print("")

            sys.stdout.flush()
            time.sleep(0.1)


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

def client_packet_received(message, packet):
    pass

##########################################################
#### Program Startup #####################################
##########################################################

# This part of the program runs at startup,
# and parses input of from the user, and then
# starts up the desired program mode.
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Speedtest example")

        parser.add_argument(
            "-s",
            "--server",
            action="store_true",
            help="wait for incoming requests from clients"
        )

        parser.add_argument(
            "--config",
            action="store",
            default=None,
            help="path to alternative Reticulum config directory",
            type=str
        )

        parser.add_argument(
            "destination",
            nargs="?",
            default=None,
            help="hexadecimal hash of the server destination",
            type=str
        )

        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        if args.server:
            server(configarg)
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
