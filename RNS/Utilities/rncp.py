#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2016-2022 Mark Qvist / unsigned.io
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import RNS
import argparse
import threading
import time
import sys
import os

from RNS._version import __version__

APP_NAME = "rncp"
allow_all = False
allow_fetch = False
fetch_jail = None
save_path = None
show_phy_rates = False
allowed_identity_hashes = []

REQ_FETCH_NOT_ALLOWED = 0xF0

es = " "
erase_str = "\33[2K\r"

def listen(configdir, verbosity = 0, quietness = 0, allowed = [], display_identity = False,
           limit = None, disable_auth = None, fetch_allowed = False, jail = None, save = None, announce = False):
    global allow_all, allow_fetch, allowed_identity_hashes, fetch_jail, save_path
    from tempfile import TemporaryFile

    allow_fetch = fetch_allowed
    identity = None
    if announce < 0:
        announce = False

    targetloglevel = 3+verbosity-quietness
    reticulum = RNS.Reticulum(configdir=configdir, loglevel=targetloglevel)

    if jail != None:
        fetch_jail = os.path.abspath(os.path.expanduser(jail))
        RNS.log("Restricting fetch requests to paths under \""+fetch_jail+"\"", RNS.LOG_VERBOSE)

    if save != None:
        sp = os.path.abspath(os.path.expanduser(save))
        if os.path.isdir(sp):
            if os.access(sp, os.W_OK):
                save_path = sp
            else:
                RNS.log("Output directory not writable", RNS.LOG_ERROR)
                exit(4)
        else:
            RNS.log("Output directory not found", RNS.LOG_ERROR)
            exit(3)

        RNS.log("Saving received files in \""+save_path+"\"", RNS.LOG_VERBOSE)

    identity_path = RNS.Reticulum.identitypath+"/"+APP_NAME
    if os.path.isfile(identity_path):
        identity = RNS.Identity.from_file(identity_path)                

    if identity == None:
        RNS.log("No valid saved identity found, creating new...", RNS.LOG_INFO)
        identity = RNS.Identity()
        identity.to_file(identity_path)

    destination = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "receive")

    if display_identity:
        print("Identity     : "+str(identity))
        print("Listening on : "+RNS.prettyhexrep(destination.hash))
        exit(0)

    if disable_auth:
        allow_all = True
    else:
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        try:
            allowed_file_name = "allowed_identities"
            allowed_file = None
            if os.path.isfile(os.path.expanduser("/etc/rncp/"+allowed_file_name)):
                allowed_file = os.path.expanduser("/etc/rncp/"+allowed_file_name)
            elif os.path.isfile(os.path.expanduser("~/.config/rncp/"+allowed_file_name)):
                allowed_file = os.path.expanduser("~/.config/rncp/"+allowed_file_name)
            elif os.path.isfile(os.path.expanduser("~/.rncp/"+allowed_file_name)):
                allowed_file = os.path.expanduser("~/.rncp/"+allowed_file_name)
            if allowed_file != None:
                af = open(allowed_file, "r")
                al = af.read().replace("\r", "").split("\n")
                ali = []
                for a in al:
                    if len(a) == dest_len:
                        ali.append(a)

                if len(ali) > 0:
                    if not allowed:
                        allowed = ali
                    else:
                        allowed.extend(ali)
                if len(ali) == 1:
                    ms = "y"
                else:
                    ms = "ies"
                
                RNS.log("Loaded "+str(len(ali))+" allowed identit"+ms+" from "+str(allowed_file), RNS.LOG_VERBOSE)

        except Exception as e:
            RNS.log("Error while parsing allowed_identities file. The contained exception was: "+str(e), RNS.LOG_ERROR)

        if allowed != None:
            for a in allowed:
                try:
                    if len(a) != dest_len:
                        raise ValueError("Allowed destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
                    try:
                        destination_hash = bytes.fromhex(a)
                        allowed_identity_hashes.append(destination_hash)
                    except Exception as e:
                        raise ValueError("Invalid destination entered. Check your input.")
                except Exception as e:
                    print(str(e))
                    exit(1)

    if len(allowed_identity_hashes) < 1 and not disable_auth:
        print("Warning: No allowed identities configured, rncp will not accept any files!")

    def fetch_request(path, data, request_id, link_id, remote_identity, requested_at):
        global allow_fetch, fetch_jail
        if not allow_fetch:
            return REQ_FETCH_NOT_ALLOWED

        if fetch_jail:
            if data.startswith(fetch_jail+"/"):
                data = data.replace(fetch_jail+"/", "")
            file_path = os.path.abspath(os.path.expanduser(f"{fetch_jail}/{data}"))
            if not file_path.startswith(fetch_jail+"/"):
                RNS.log(f"Disallowing fetch request for {file_path} outside of fetch jail {fetch_jail}", RNS.LOG_WARNING)
                return REQ_FETCH_NOT_ALLOWED
        else:
            file_path = os.path.abspath(os.path.expanduser(f"{data}"))

        target_link = None
        for link in RNS.Transport.active_links:
            if link.link_id == link_id:
                target_link = link

        if not os.path.isfile(file_path):
            RNS.log("Client-requested file not found: "+str(file_path), RNS.LOG_VERBOSE)
            return False
        else:
            if target_link != None:
                RNS.log("Sending file "+str(file_path)+" to client", RNS.LOG_VERBOSE)

                temp_file = TemporaryFile()
                real_file = open(file_path, "rb")
                filename_bytes = os.path.basename(file_path).encode("utf-8")
                filename_len = len(filename_bytes)

                if filename_len > 0xFFFF:
                    print("Filename exceeds max size, cannot send")
                    exit(1)

                temp_file.write(filename_len.to_bytes(2, "big"))
                temp_file.write(filename_bytes)
                temp_file.write(real_file.read())
                temp_file.seek(0)

                fetch_resource = RNS.Resource(temp_file, target_link)
                return True
            else:
                return None


    destination.set_link_established_callback(client_link_established)
    if allow_fetch:
        if allow_all:
            RNS.log("Allowing unauthenticated fetch requests", RNS.LOG_WARNING)
            destination.register_request_handler("fetch_file", response_generator=fetch_request, allow=RNS.Destination.ALLOW_ALL)
        else:
            destination.register_request_handler("fetch_file", response_generator=fetch_request, allow=RNS.Destination.ALLOW_LIST, allowed_list=allowed_identity_hashes)

    print("rncp listening on "+RNS.prettyhexrep(destination.hash))

    if announce >= 0:
        def job():
            destination.announce()
            if announce > 0:
                while True:
                    time.sleep(announce)
                    destination.announce()

        threading.Thread(target=job, daemon=True).start()
    
    while True:
        time.sleep(1)

def client_link_established(link):
    RNS.log("Incoming link established", RNS.LOG_VERBOSE)
    link.set_remote_identified_callback(receive_sender_identified)
    link.set_resource_strategy(RNS.Link.ACCEPT_APP)
    link.set_resource_callback(receive_resource_callback)
    link.set_resource_started_callback(receive_resource_started)
    link.set_resource_concluded_callback(receive_resource_concluded)

def receive_sender_identified(link, identity):
    global allow_all

    if identity.hash in allowed_identity_hashes:
        RNS.log("Authenticated sender", RNS.LOG_VERBOSE)
    else:
        if not allow_all:
            RNS.log("Sender not allowed, tearing down link", RNS.LOG_VERBOSE)
            link.teardown()
        else:
            pass

def receive_resource_callback(resource):
    global allow_all
    
    sender_identity = resource.link.get_remote_identity()

    if sender_identity != None:
        if sender_identity.hash in allowed_identity_hashes:
            return True

    if allow_all:
        return True

    return False

def receive_resource_started(resource):
    if resource.link.get_remote_identity():
        id_str = " from "+RNS.prettyhexrep(resource.link.get_remote_identity().hash)
    else:
        id_str = ""

    print("Starting resource transfer "+RNS.prettyhexrep(resource.hash)+id_str)

def receive_resource_concluded(resource):
    global save_path
    if resource.status == RNS.Resource.COMPLETE:
        print(str(resource)+" completed")

        if resource.total_size > 4:
            filename_len = int.from_bytes(resource.data.read(2), "big")
            filename = resource.data.read(filename_len).decode("utf-8")

            counter = 0
            if save_path:
                saved_filename = os.path.abspath(os.path.expanduser(save_path+"/"+filename))
                if not saved_filename.startswith(save_path+"/"):
                    RNS.log(f"Invalid save path {saved_filename}, ignoring", RNS.LOG_ERROR)
                    return
            else:
                saved_filename = filename

            full_save_path = saved_filename
            while os.path.isfile(full_save_path):
                counter += 1
                full_save_path = saved_filename+"."+str(counter)
            
            file = open(full_save_path, "wb")
            file.write(resource.data.read())
            file.close()

        else:
            print("Invalid data received, ignoring resource")

    else:
        print("Resource failed")

resource_done = False
current_resource = None
stats = []
speed = 0.0
phy_speed = 0.0
def sender_progress(resource):
    stats_max = 32
    global current_resource, stats, speed, phy_speed, resource_done
    current_resource = resource
    
    now = time.time()
    got = current_resource.get_progress()*current_resource.get_data_size()
    phy_got = current_resource.get_segment_progress()*current_resource.get_transfer_size()
    
    entry = [now, got, phy_got]
    stats.append(entry)

    while len(stats) > stats_max:
        stats.pop(0)

    span = now - stats[0][0]
    if span == 0:
        speed = 0
        phy_speed = 0
    
    else:
        diff = got - stats[0][1]
        speed = diff/span

        phy_diff = phy_got - stats[0][2]
        if phy_diff > 0:
            phy_speed = phy_diff/span

    if resource.status < RNS.Resource.COMPLETE:
        resource_done = False
    else:
        resource_done = True

link = None
def fetch(configdir, verbosity = 0, quietness = 0, destination = None, file = None, timeout = RNS.Transport.PATH_REQUEST_TIMEOUT, silent=False, phy_rates=False, save=None):
    global current_resource, resource_done, link, speed, show_phy_rates, save_path
    targetloglevel = 3+verbosity-quietness
    show_phy_rates = phy_rates

    if save:
        sp = os.path.abspath(os.path.expanduser(save))
        if os.path.isdir(sp):
            if os.access(sp, os.W_OK):
                save_path = sp
            else:
                RNS.log("Output directory not writable", RNS.LOG_ERROR)
                exit(4)
        else:
            RNS.log("Output directory not found", RNS.LOG_ERROR)
            exit(3)

    try:
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        if len(destination) != dest_len:
            raise ValueError("Allowed destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
        try:
            destination_hash = bytes.fromhex(destination)
        except Exception as e:
            raise ValueError("Invalid destination entered. Check your input.")
    except Exception as e:
        print(str(e))
        exit(1)

    reticulum = RNS.Reticulum(configdir=configdir, loglevel=targetloglevel)

    identity_path = RNS.Reticulum.identitypath+"/"+APP_NAME
    if os.path.isfile(identity_path):
        identity = RNS.Identity.from_file(identity_path)
        if identity == None:
            RNS.log("Could not load identity for rncp. The identity file at \""+str(identity_path)+"\" may be corrupt or unreadable.", RNS.LOG_ERROR)
            exit(2)
    else:
        identity = None

    if identity == None:
        RNS.log("No valid saved identity found, creating new...", RNS.LOG_INFO)
        identity = RNS.Identity()
        identity.to_file(identity_path)

    if not RNS.Transport.has_path(destination_hash):
        RNS.Transport.request_path(destination_hash)
        if silent:
            print("Path to "+RNS.prettyhexrep(destination_hash)+" requested")
        else:
            print("Path to "+RNS.prettyhexrep(destination_hash)+" requested  ", end=es)
        sys.stdout.flush()

    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    estab_timeout = time.time()+timeout
    while not RNS.Transport.has_path(destination_hash) and time.time() < estab_timeout:
        if not silent:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

    if not RNS.Transport.has_path(destination_hash):
        if silent:
            print("Path not found")
        else:
            print(f"{erase_str}Path not found")
        exit(1)
    else:
        if silent:
            print("Establishing link with "+RNS.prettyhexrep(destination_hash))
        else:
            print(f"{erase_str}Establishing link with "+RNS.prettyhexrep(destination_hash)+"  ", end=es)

    listener_identity = RNS.Identity.recall(destination_hash)
    listener_destination = RNS.Destination(
        listener_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        APP_NAME,
        "receive"
    )

    link = RNS.Link(listener_destination)
    while link.status != RNS.Link.ACTIVE and time.time() < estab_timeout:
        if not silent:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

    if not RNS.Transport.has_path(destination_hash):
        if silent:
            print("Could not establish link with "+RNS.prettyhexrep(destination_hash))
        else:
            print(f"{erase_str}Could not establish link with "+RNS.prettyhexrep(destination_hash))
        exit(1)
    else:
        if silent:
            print("Requesting file from remote...")
        else:
            print(f"{erase_str}Requesting file from remote  ", end=es)

    link.identify(identity)

    request_resolved = False
    request_status = "unknown"
    resource_resolved = False
    resource_status = "unrequested"
    current_resource = None
    def request_response(request_receipt):
        nonlocal request_resolved, request_status
        if request_receipt.response == False:
            request_status = "not_found"
        elif request_receipt.response == None:
            request_status = "remote_error"
        elif request_receipt.response == REQ_FETCH_NOT_ALLOWED:
            request_status = "fetch_not_allowed"
        else:
            request_status = "found"

        request_resolved = True

    def request_failed(request_receipt):
        nonlocal request_resolved, request_status
        request_status = "unknown"
        request_resolved = True

    def fetch_resource_started(resource):
        nonlocal resource_status
        current_resource = resource
        current_resource.progress_callback(sender_progress)
        resource_status = "started"

    def fetch_resource_concluded(resource):
        nonlocal resource_resolved, resource_status
        global save_path
        if resource.status == RNS.Resource.COMPLETE:
            if resource.total_size > 4:
                filename_len = int.from_bytes(resource.data.read(2), "big")
                filename = resource.data.read(filename_len).decode("utf-8")

                counter = 0
                if save_path:
                    saved_filename = os.path.abspath(os.path.expanduser(save_path+"/"+filename))

                else:
                    saved_filename = filename

                full_save_path = saved_filename
                while os.path.isfile(full_save_path):
                    counter += 1
                    full_save_path = saved_filename+"."+str(counter)
 
                file = open(full_save_path, "wb")
                file.write(resource.data.read())
                file.close()
                resource_status = "completed"

            else:
                print("Invalid data received, ignoring resource")
                resource_status = "invalid_data"

        else:
            print("Resource failed")
            resource_status = "failed"

        resource_resolved = True

    link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
    link.set_resource_started_callback(fetch_resource_started)
    link.set_resource_concluded_callback(fetch_resource_concluded)
    link.request("fetch_file", data=file, response_callback=request_response, failed_callback=request_failed)

    syms = "⢄⢂⢁⡁⡈⡐⡠"
    while not request_resolved:
        if not silent:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

    if request_status == "fetch_not_allowed":
        if not silent: print(f"{erase_str}", end="")
        print("Fetch request failed, fetching the file "+str(file)+" was not allowed by the remote")
        link.teardown()
        time.sleep(0.15)
        exit(0)
    elif request_status == "not_found":
        if not silent: print(f"{erase_str}", end="")
        print("Fetch request failed, the file "+str(file)+" was not found on the remote")
        link.teardown()
        time.sleep(0.15)
        exit(0)
    elif request_status == "remote_error":
        if not silent: print(f"{erase_str}", end="")
        print("Fetch request failed due to an error on the remote system")
        link.teardown()
        time.sleep(0.15)
        exit(0)
    elif request_status == "unknown":
        if not silent: print(f"{erase_str}", end="")
        print("Fetch request failed due to an unknown error (probably not authorised)")
        link.teardown()
        time.sleep(0.15)
        exit(0)
    elif request_status == "found":
        if not silent: print(f"{erase_str}", end="")

    while not resource_resolved:
        if not silent:
            time.sleep(0.1)
            if current_resource:
                prg = current_resource.get_progress()
                percent = round(prg * 100.0, 1)
                if show_phy_rates:
                    pss = size_str(phy_speed, "b")
                    phy_str = f" ({pss}ps at physical layer)"
                else:
                    phy_str = ""
                ps = size_str(int(prg*current_resource.total_size))
                ts = size_str(current_resource.total_size)
                ss = size_str(speed, "b")
                stat_str = f"{percent}% - {ps} of {ts} - {ss}ps{phy_str}"
                if prg != 1.0:
                    print(f"{erase_str}Transferring file {syms[i]} {stat_str}", end=es)
                else:
                    print(f"{erase_str}Transfer complete  {stat_str}", end=es)
            else:
                print(f"{erase_str}Waiting for transfer to start {syms[i]} ", end=es)
            sys.stdout.flush()
            i = (i+1)%len(syms)

    if current_resource.status != RNS.Resource.COMPLETE:
        if silent:
            print("The transfer failed")
        else:
            print(f"{erase_str}The transfer failed")
        exit(1)
    else:
        if silent:
            print(str(file)+" fetched from "+RNS.prettyhexrep(destination_hash))
        else:
            print("\n"+str(file)+" fetched from "+RNS.prettyhexrep(destination_hash))
        link.teardown()
        time.sleep(0.15)
        exit(0)

    link.teardown()
    exit(0)


def send(configdir, verbosity = 0, quietness = 0, destination = None, file = None, timeout = RNS.Transport.PATH_REQUEST_TIMEOUT, silent=False, phy_rates=False):
    global current_resource, resource_done, link, speed, show_phy_rates
    from tempfile import TemporaryFile
    targetloglevel = 3+verbosity-quietness
    show_phy_rates = phy_rates

    try:
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        if len(destination) != dest_len:
            raise ValueError("Allowed destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
        try:
            destination_hash = bytes.fromhex(destination)
        except Exception as e:
            raise ValueError("Invalid destination entered. Check your input.")
    except Exception as e:
        print(str(e))
        exit(1)

    
    file_path = os.path.expanduser(file)
    if not os.path.isfile(file_path):
        print("File not found")
        exit(1)

    temp_file = TemporaryFile()
    real_file = open(file_path, "rb")
    filename_bytes = os.path.basename(file_path).encode("utf-8")
    filename_len = len(filename_bytes)

    if filename_len > 0xFFFF:
        print("Filename exceeds max size, cannot send")
        exit(1)
    else:
        print("Preparing file...", end=es)

    temp_file.write(filename_len.to_bytes(2, "big"))
    temp_file.write(filename_bytes)
    temp_file.write(real_file.read())
    temp_file.seek(0)

    print(f"{erase_str}", end="")

    reticulum = RNS.Reticulum(configdir=configdir, loglevel=targetloglevel)

    identity_path = RNS.Reticulum.identitypath+"/"+APP_NAME
    if os.path.isfile(identity_path):
        identity = RNS.Identity.from_file(identity_path)
        if identity == None:
            RNS.log("Could not load identity for rncp. The identity file at \""+str(identity_path)+"\" may be corrupt or unreadable.", RNS.LOG_ERROR)
            exit(2)
    else:
        identity = None

    if identity == None:
        RNS.log("No valid saved identity found, creating new...", RNS.LOG_INFO)
        identity = RNS.Identity()
        identity.to_file(identity_path)

    if not RNS.Transport.has_path(destination_hash):
        RNS.Transport.request_path(destination_hash)
        if silent:
            print("Path to "+RNS.prettyhexrep(destination_hash)+" requested")
        else:
            print("Path to "+RNS.prettyhexrep(destination_hash)+" requested  ", end=es)
        sys.stdout.flush()

    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    estab_timeout = time.time()+timeout
    while not RNS.Transport.has_path(destination_hash) and time.time() < estab_timeout:
        if not silent:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

    if not RNS.Transport.has_path(destination_hash):
        if silent:
            print("Path not found")
        else:
            print(f"{erase_str}Path not found")
        exit(1)
    else:
        if silent:
            print("Establishing link with "+RNS.prettyhexrep(destination_hash))
        else:
            print(f"{erase_str}Establishing link with "+RNS.prettyhexrep(destination_hash)+" ", end=es)

    receiver_identity = RNS.Identity.recall(destination_hash)
    receiver_destination = RNS.Destination(
        receiver_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        APP_NAME,
        "receive"
    )

    link = RNS.Link(receiver_destination)
    while link.status != RNS.Link.ACTIVE and time.time() < estab_timeout:
        if not silent:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

    if time.time() > estab_timeout:
        if silent:
            print("Link establishment with "+RNS.prettyhexrep(destination_hash)+" timed out")
        else:
            print(f"{erase_str}Link establishment with "+RNS.prettyhexrep(destination_hash)+" timed out")
        exit(1)
    elif not RNS.Transport.has_path(destination_hash):
        if silent:
            print("No path found to "+RNS.prettyhexrep(destination_hash))
        else:
            print(f"{erase_str}No path found to "+RNS.prettyhexrep(destination_hash))
        exit(1)
    else:
        if silent:
            print("Advertising file resource...")
        else:
            print(f"{erase_str}Advertising file resource  ", end=es)

    link.identify(identity)
    resource = RNS.Resource(temp_file, link, callback = sender_progress, progress_callback = sender_progress)
    current_resource = resource

    while resource.status < RNS.Resource.TRANSFERRING:
        if not silent:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

    
    if resource.status > RNS.Resource.COMPLETE:
        if silent:
            print("File was not accepted by "+RNS.prettyhexrep(destination_hash))
        else:
            print(f"{erase_str}File was not accepted by "+RNS.prettyhexrep(destination_hash))
        exit(1)
    else:
        if silent:
            print("Transferring file...")
        else:
            print(f"{erase_str}Transferring file  ", end=es)

    def progress_update(i, done=False):
        time.sleep(0.1)
        prg = current_resource.get_progress()
        percent = round(prg * 100.0, 1)
        if show_phy_rates:
            pss = size_str(phy_speed, "b")
            phy_str = f" ({pss}ps at physical layer)"
        else:
            phy_str = ""
        es = "  "
        cs = size_str(int(prg*current_resource.total_size))
        ts = size_str(current_resource.total_size)
        ss = size_str(speed, "b")
        stat_str = f"{percent}% - {cs} of {ts} - {ss}ps{phy_str}"
        if not done:
            print(f"{erase_str}Transferring file "+syms[i]+" "+stat_str, end=es)
        else:
            print(f"{erase_str}Transfer complete  "+stat_str, end=es)
        sys.stdout.flush()
        i = (i+1)%len(syms)
        return i

    while not resource_done:
        if not silent:
            i = progress_update(i)

    if not silent:
        i = progress_update(i, done=True)

    if current_resource.status != RNS.Resource.COMPLETE:
        if silent:
            print("The transfer failed")
        else:
            print(f"{erase_str}The transfer failed")
        exit(1)
    else:
        if silent:
            print(str(file_path)+" copied to "+RNS.prettyhexrep(destination_hash))
        else:
            print("\n"+str(file_path)+" copied to "+RNS.prettyhexrep(destination_hash))
        link.teardown()
        time.sleep(0.25)
        real_file.close()
        temp_file.close()
        exit(0)

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum File Transfer Utility")
        parser.add_argument("file", nargs="?", default=None, help="file to be transferred", type=str)
        parser.add_argument("destination", nargs="?", default=None, help="hexadecimal hash of the receiver", type=str)
        parser.add_argument("--config", metavar="path", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-v', '--verbose', action='count', default=0, help="increase verbosity")
        parser.add_argument('-q', '--quiet', action='count', default=0, help="decrease verbosity")
        parser.add_argument("-S", '--silent', action='store_true', default=False, help="disable transfer progress output")
        parser.add_argument("-l", '--listen', action='store_true', default=False, help="listen for incoming transfer requests")
        parser.add_argument("-F", '--allow-fetch', action='store_true', default=False, help="allow authenticated clients to fetch files")
        parser.add_argument("-f", '--fetch', action='store_true', default=False, help="fetch file from remote listener instead of sending")
        parser.add_argument("-j", "--jail", metavar="path", action="store", default=None, help="restrict fetch requests to specified path", type=str)
        parser.add_argument("-s", "--save", metavar="path", action="store", default=None, help="save received files in specified path", type=str)
        parser.add_argument("-b", action='store', metavar="seconds", default=-1, help="announce interval, 0 to only announce at startup", type=int)
        parser.add_argument('-a', metavar="allowed_hash", dest="allowed", action='append', help="allow this identity (or add in ~/.rncp/allowed_identities)", type=str)
        parser.add_argument('-n', '--no-auth', action='store_true', default=False, help="accept requests from anyone")
        parser.add_argument('-p', '--print-identity', action='store_true', default=False, help="print identity and destination info and exit")
        parser.add_argument("-w", action="store", metavar="seconds", type=float, help="sender timeout before giving up", default=RNS.Transport.PATH_REQUEST_TIMEOUT)
        parser.add_argument('-P', '--phy-rates', action='store_true', default=False, help="display physical layer transfer rates")
        # parser.add_argument("--limit", action="store", metavar="files", type=float, help="maximum number of files to accept", default=None)
        parser.add_argument("--version", action="version", version="rncp {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.listen or args.print_identity:
            listen(
                configdir = args.config,
                verbosity=args.verbose,
                quietness=args.quiet,
                allowed = args.allowed,
                fetch_allowed = args.allow_fetch,
                jail = args.jail,
                save = args.save,
                display_identity=args.print_identity,
                # limit=args.limit,
                disable_auth=args.no_auth,
                announce=args.b,
            )

        elif args.fetch:
            if args.destination != None and args.file != None:
                fetch(
                    configdir = args.config,
                    verbosity = args.verbose,
                    quietness = args.quiet,
                    destination = args.destination,
                    file = args.file,
                    timeout = args.w,
                    silent = args.silent,
                    phy_rates = args.phy_rates,
                    save = args.save,
                )
            else:
                print("")
                parser.print_help()
                print("")

        elif args.destination != None and args.file != None:
            send(
                configdir = args.config,
                verbosity = args.verbose,
                quietness = args.quiet,
                destination = args.destination,
                file = args.file,
                timeout = args.w,
                silent = args.silent,
                phy_rates = args.phy_rates,
            )

        else:
            print("")
            parser.print_help()
            print("")

    except KeyboardInterrupt:
        print("")
        if resource != None:
            resource.cancel()
        if link != None:
            link.teardown()
        exit()

def size_str(num, suffix='B'):
    units = ['','K','M','G','T','P','E','Z']
    last_unit = 'Y'

    if suffix == 'b':
        num *= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1000.0:
            if unit == "":
                return "%.0f %s%s" % (num, unit, suffix)
            else:
                return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

if __name__ == "__main__":
    main()
