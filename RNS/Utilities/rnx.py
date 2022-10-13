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
import subprocess
import argparse
import shlex
import time
import sys
import tty
import os

from RNS._version import __version__

APP_NAME = "rnx"
identity = None
reticulum = None
allow_all = False
allowed_identity_hashes = []

def prepare_identity(identity_path):
    global identity
    if identity_path == None:
        identity_path = RNS.Reticulum.identitypath+"/"+APP_NAME

    if os.path.isfile(identity_path):
        identity = RNS.Identity.from_file(identity_path)                

    if identity == None:
        RNS.log("No valid saved identity found, creating new...", RNS.LOG_INFO)
        identity = RNS.Identity()
        identity.to_file(identity_path)

def listen(configdir, identitypath = None, verbosity = 0, quietness = 0, allowed = [], print_identity = False, disable_auth = None, disable_announce=False):
    global identity, allow_all, allowed_identity_hashes, reticulum

    targetloglevel = 3+verbosity-quietness
    reticulum = RNS.Reticulum(configdir=configdir, loglevel=targetloglevel)
    
    prepare_identity(identitypath)
    destination = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "execute")

    if print_identity:
        print("Identity     : "+str(identity))
        print("Listening on : "+RNS.prettyhexrep(destination.hash))
        exit(0)

    if disable_auth:
        allow_all = True
    else:
        if allowed != None:
            for a in allowed:
                try:
                    dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
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
        print("Warning: No allowed identities configured, rncx will not accept any commands!")

    destination.set_link_established_callback(command_link_established)

    if not allow_all:
        destination.register_request_handler(
            path = "command",
            response_generator = execute_received_command,
            allow = RNS.Destination.ALLOW_LIST,
            allowed_list = allowed_identity_hashes
        )
    else:
        destination.register_request_handler(
            path = "command",
            response_generator = execute_received_command,
            allow = RNS.Destination.ALLOW_ALL,
        )

    RNS.log("rnx listening for commands on "+RNS.prettyhexrep(destination.hash))

    if not disable_announce:
        destination.announce()
    
    while True:
        time.sleep(1)

def command_link_established(link):
    link.set_remote_identified_callback(initiator_identified)
    link.set_link_closed_callback(command_link_closed)
    RNS.log("Command link "+str(link)+" established")

def command_link_closed(link):
    RNS.log("Command link "+str(link)+" closed")

def initiator_identified(link, identity):
    global allow_all
    RNS.log("Initiator of link "+str(link)+" identified as "+RNS.prettyhexrep(identity.hash))
    if not allow_all and not identity.hash in allowed_identity_hashes:
        RNS.log("Identity "+RNS.prettyhexrep(identity.hash)+" not allowed, tearing down link")
        link.teardown()

def execute_received_command(path, data, request_id, remote_identity, requested_at):
    command = data[0].decode("utf-8")  # Command to execute
    timeout = data[1]                  # Timeout in seconds
    o_limit = data[2]                  # Size limit for stdout
    e_limit = data[3]                  # Size limit for stderr
    stdin   = data[4]                  # Data passed to stdin

    if remote_identity != None:
        RNS.log("Executing command ["+command+"] for "+RNS.prettyhexrep(remote_identity.hash))
    else:
        RNS.log("Executing command ["+command+"] for unknown requestor")

    result    = [
        False,                         # 0: Command was executed
        None,                          # 1: Return value
        None,                          # 2: Stdout
        None,                          # 3: Stderr
        None,                          # 4: Total stdout length
        None,                          # 5: Total stderr length
        time.time(),                   # 6: Started
        None,                          # 7: Concluded
    ]

    try:
        process = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result[0] = True

    except Exception as e:
        result[0] = False
        return result

    stdout = b""
    stderr = b""
    timed_out = False

    if stdin != None:
        process.stdin.write(stdin)

    while True:
        try:
            stdout, stderr = process.communicate(timeout=1)
            if process.poll() != None:
                break

            if len(stdout) > 0:
                print(str(stdout))
                sys.stdout.flush()

        except subprocess.TimeoutExpired:
            pass

        if timeout != None and time.time() > result[6]+timeout:
            RNS.log("Command ["+command+"] timed out and is being killed...")
            process.terminate()
            process.wait()
            if process.poll() != None:
                stdout, stderr = process.communicate()
            else:
                stdout = None
                stderr = None

            break

    if timeout != None and time.time() < result[6]+timeout:
        result[7] = time.time()

    # Deliver result
    result[1] = process.returncode

    if o_limit != None and len(stdout) > o_limit:
        if o_limit == 0:
            result[2] = b""
        else:
            result[2] = stdout[0:o_limit]
    else:
        result[2] = stdout

    if e_limit != None and len(stderr) > e_limit:
        if e_limit == 0:
            result[3] = b""
        else:
            result[3] = stderr[0:e_limit]
    else:
        result[3] = stderr

    result[4] = len(stdout)
    result[5] = len(stderr)

    if timed_out:
        RNS.log("Command timed out")
        return result

    if remote_identity != None:
        RNS.log("Delivering result of command ["+str(command)+"] to "+RNS.prettyhexrep(remote_identity.hash))
    else:
        RNS.log("Delivering result of command ["+str(command)+"] to unknown requestor")

    return result

def spin(until=None, msg=None, timeout=None):
    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    if timeout != None:
        timeout = time.time()+timeout

    print(msg+"  ", end=" ")
    while (timeout == None or time.time()<timeout) and not until():
        time.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    print("\r"+" "*len(msg)+"  \r", end="")

    if timeout != None and time.time() > timeout:
        return False
    else:
        return True

current_progress = 0.0
stats = []
speed = 0.0
def spin_stat(until=None, timeout=None):
    global current_progress, response_transfer_size, speed
    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    if timeout != None:
        timeout = time.time()+timeout

    while (timeout == None or time.time()<timeout) and not until():
        time.sleep(0.1)
        prg = current_progress
        percent = round(prg * 100.0, 1)
        stat_str = str(percent)+"% - " + size_str(int(prg*response_transfer_size)) + " of " + size_str(response_transfer_size) + " - " +size_str(speed, "b")+"ps"
        print("\r                                                                                  \rReceiving result "+syms[i]+" "+stat_str, end=" ")

        sys.stdout.flush()
        i = (i+1)%len(syms)

    print("\r                                                                                  \r", end="")

    if timeout != None and time.time() > timeout:
        return False
    else:
        return True

def remote_execution_done(request_receipt):
    pass

def remote_execution_progress(request_receipt):
    stats_max = 32
    global current_progress, response_transfer_size, speed
    current_progress = request_receipt.progress
    response_transfer_size = request_receipt.response_transfer_size
    now = time.time()
    got = current_progress*response_transfer_size
    entry = [now, got]
    stats.append(entry)
    while len(stats) > stats_max:
        stats.pop(0)

    span = now - stats[0][0]
    if span == 0:
        speed = 0
    else:
        diff = got - stats[0][1]
        speed = diff/span

link = None
listener_destination = None
remote_exec_grace = 2.0
def execute(configdir, identitypath = None, verbosity = 0, quietness = 0, detailed = False, mirror = False, noid = False, destination = None, command = None, stdin = None, stdoutl = None, stderrl = None, timeout = RNS.Transport.PATH_REQUEST_TIMEOUT, result_timeout = None, interactive = False):
    global identity, reticulum, link, listener_destination, remote_exec_grace

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
        exit(241)

    if reticulum == None:
        targetloglevel = 3+verbosity-quietness
        reticulum = RNS.Reticulum(configdir=configdir, loglevel=targetloglevel)

    if identity == None:
        prepare_identity(identitypath)

    if not RNS.Transport.has_path(destination_hash):
        RNS.Transport.request_path(destination_hash)
        if not spin(until=lambda: RNS.Transport.has_path(destination_hash), msg="Path to "+RNS.prettyhexrep(destination_hash)+" requested", timeout=timeout):
            print("Path not found")
            exit(242)

    if listener_destination == None:
        listener_identity = RNS.Identity.recall(destination_hash)
        listener_destination = RNS.Destination(
            listener_identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            APP_NAME,
            "execute"
        )

    if link == None or link.status == RNS.Link.CLOSED or link.status == RNS.Link.PENDING:
        link = RNS.Link(listener_destination)
        link.did_identify = False
    
    if not spin(until=lambda: link.status == RNS.Link.ACTIVE, msg="Establishing link with "+RNS.prettyhexrep(destination_hash), timeout=timeout):
        print("Could not establish link with "+RNS.prettyhexrep(destination_hash))
        exit(243)

    if not noid and not link.did_identify:
        link.identify(identity)
        link.did_identify = True

    if stdin != None:
        stdin = stdin.encode("utf-8")

    request_data = [
        command.encode("utf-8"),  # Command to execute
        timeout,                  # Timeout in seconds
        stdoutl,                  # Size limit for stdout
        stderrl,                  # Size limit for stderr
        stdin,                    # Data passed to stdin
    ]

    # TODO: Tune
    rexec_timeout = timeout+link.rtt*4+remote_exec_grace

    request_receipt = link.request(
        path="command",
        data=request_data,
        response_callback=remote_execution_done,
        failed_callback=remote_execution_done,
        progress_callback=remote_execution_progress,
        timeout=rexec_timeout
    )

    spin(
        until=lambda:link.status == RNS.Link.CLOSED or (request_receipt.status != RNS.RequestReceipt.FAILED and request_receipt.status != RNS.RequestReceipt.SENT),
        msg="Sending execution request",
        timeout=rexec_timeout+0.5
    )

    if link.status == RNS.Link.CLOSED:
        print("Could not request remote execution, link was closed")
        exit(244)

    if request_receipt.status == RNS.RequestReceipt.FAILED:
        print("Could not request remote execution")
        if interactive:
            return
        else:
            exit(244)

    spin(
        until=lambda:request_receipt.status != RNS.RequestReceipt.DELIVERED,
        msg="Command delivered, awaiting result",
        timeout=timeout
    )

    if request_receipt.status == RNS.RequestReceipt.FAILED:
        print("No result was received")
        if interactive:
            return
        else:
            exit(245)

    spin_stat(
        until=lambda:request_receipt.status != RNS.RequestReceipt.RECEIVING,
        timeout=result_timeout
    )

    if request_receipt.status == RNS.RequestReceipt.FAILED:
        print("Receiving result failed")
        if interactive:
            return
        else:
            exit(246)

    if request_receipt.response != None:
        try:
            executed = request_receipt.response[0]
            retval = request_receipt.response[1]
            stdout = request_receipt.response[2]
            stderr = request_receipt.response[3]
            outlen = request_receipt.response[4]
            errlen = request_receipt.response[5]
            started = request_receipt.response[6]
            concluded = request_receipt.response[7]

        except Exception as e:
            print("Received invalid result")
            if interactive:
                return
            else:
                exit(247)

        if executed:
            if detailed:
                if stdout != None and len(stdout) > 0:
                    print(stdout.decode("utf-8"), end="")
                if stderr != None and len(stderr) > 0:
                    print(stderr.decode("utf-8"), file=sys.stderr, end="")

                sys.stdout.flush()
                sys.stderr.flush()

                print("\n--- End of remote output, rnx done ---")
                if started != None and concluded != None:
                    cmd_duration = round(concluded - started, 3)
                    print("Remote command execution took "+str(cmd_duration)+" seconds")

                    total_size = request_receipt.response_size
                    if request_receipt.request_size != None:
                        total_size += request_receipt.request_size

                    transfer_duration = round(request_receipt.response_concluded_at - request_receipt.sent_at - cmd_duration, 3)
                    if transfer_duration == 1:
                        tdstr = " in 1 second"
                    elif transfer_duration < 10:
                        tdstr = " in "+str(transfer_duration)+" seconds"
                    else:
                        tdstr = " in "+pretty_time(transfer_duration)

                    spdstr = ", effective rate "+size_str(total_size/transfer_duration, "b")+"ps"

                    print("Transferred "+size_str(total_size)+tdstr+spdstr)

                if outlen != None and stdout != None:
                    if len(stdout) < outlen:
                        tstr = ", "+str(len(stdout))+" bytes displayed"
                    else:
                        tstr = ""
                    print("Remote wrote "+str(outlen)+" bytes to stdout"+tstr)
                
                if errlen != None and stderr != None:
                    if len(stderr) < errlen:
                        tstr = ", "+str(len(stderr))+" bytes displayed"
                    else:
                        tstr = ""
                    print("Remote wrote "+str(errlen)+" bytes to stderr"+tstr)

            else:
                if stdout != None and len(stdout) > 0:
                    print(stdout.decode("utf-8"), end="")
                if stderr != None and len(stderr) > 0:
                    print(stderr.decode("utf-8"), file=sys.stderr, end="")


                if (stdoutl != 0 and len(stdout) < outlen) or (stderrl != 0 and len(stderr) < errlen):
                    sys.stdout.flush()
                    sys.stderr.flush()
                    print("\nOutput truncated before being returned:")
                    if len(stdout) != 0 and len(stdout) < outlen:
                        print("  stdout truncated to "+str(len(stdout))+" bytes")
                    if len(stderr) != 0 and len(stderr) < errlen:
                        print("  stderr truncated to "+str(len(stderr))+" bytes")
        else:
            print("Remote could not execute command")
            if interactive:
                return
            else:
                exit(248)
    else:
        print("No response")
        if interactive:
            return
        else:
            exit(249)

    try:
        if not interactive:
            link.teardown()

    except Exception as e:
        pass

    if not interactive and mirror:
        if request_receipt.response[1] != None:
            exit(request_receipt.response[1])
        else:
            exit(240)
    else:
        if interactive:
            if mirror:
                return request_receipt.response[1]
            else:
                return None
        else:
            exit(0)

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Remote Execution Utility")
        parser.add_argument("destination", nargs="?", default=None, help="hexadecimal hash of the listener", type=str)
        parser.add_argument("command", nargs="?", default=None, help="command to be execute", type=str)
        parser.add_argument("--config", metavar="path", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-v', '--verbose', action='count', default=0, help="increase verbosity")
        parser.add_argument('-q', '--quiet', action='count', default=0, help="decrease verbosity")
        parser.add_argument('-p', '--print-identity', action='store_true', default=False, help="print identity and destination info and exit")
        parser.add_argument("-l", '--listen', action='store_true', default=False, help="listen for incoming commands")
        parser.add_argument('-i', metavar="identity", action='store', dest="identity", default=None, help="path to identity to use", type=str)
        parser.add_argument("-x", '--interactive', action='store_true', default=False, help="enter interactive mode")
        parser.add_argument("-b", '--no-announce', action='store_true', default=False, help="don't announce at program start")
        parser.add_argument('-a', metavar="allowed_hash", dest="allowed", action='append', help="accept from this identity", type=str)
        parser.add_argument('-n', '--noauth', action='store_true', default=False, help="accept commands from anyone")
        parser.add_argument('-N', '--noid', action='store_true', default=False, help="don't identify to listener")
        parser.add_argument("-d", '--detailed', action='store_true', default=False, help="show detailed result output")
        parser.add_argument("-m", action='store_true', dest="mirror", default=False, help="mirror exit code of remote command")
        parser.add_argument("-w", action="store", metavar="seconds", type=float, help="connect and request timeout before giving up", default=RNS.Transport.PATH_REQUEST_TIMEOUT)
        parser.add_argument("-W", action="store", metavar="seconds", type=float, help="max result download time", default=None)
        parser.add_argument("--stdin", action='store', default=None, help="pass input to stdin", type=str)
        parser.add_argument("--stdout", action='store', default=None, help="max size in bytes of returned stdout", type=int)
        parser.add_argument("--stderr", action='store', default=None, help="max size in bytes of returned stderr", type=int)
        parser.add_argument("--version", action="version", version="rnx {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.listen or args.print_identity:
            listen(
                configdir = args.config,
                identitypath = args.identity,
                verbosity=args.verbose,
                quietness=args.quiet,
                allowed = args.allowed,
                print_identity=args.print_identity,
                disable_auth=args.noauth,
                disable_announce=args.no_announce,
            )

        elif args.destination != None and args.command != None:
            execute(
                configdir = args.config,
                identitypath = args.identity,
                verbosity = args.verbose,
                quietness = args.quiet,
                detailed = args.detailed,
                mirror = args.mirror,
                noid = args.noid,
                destination = args.destination,
                command = args.command,
                stdin = args.stdin,
                stdoutl = args.stdout,
                stderrl = args.stderr,
                timeout = args.w,
                result_timeout = args.W,
                interactive = args.interactive,
            )

        if args.destination != None and args.interactive:
            # command_history_max = 5000
            # command_history = []
            # command_current = ""
            # history_idx = 0
            # tty.setcbreak(sys.stdin.fileno())

            code = None
            while True:
                try:
                    cstr = str(code) if code and code != 0 else ""
                    prompt = cstr+"> "
                    print(prompt,end="")

                    # cmdbuf = b""
                    # while True:
                    #     ch = sys.stdin.read(1)
                    #     cmdbuf += ch.encode("utf-8")
                    #     print("\r"+prompt+cmdbuf.decode("utf-8"), end="")    
                    
                    command = input()
                    if command.lower() == "exit" or command.lower() == "quit":
                        exit(0)

                except KeyboardInterrupt:
                    exit(0)
                except EOFError:
                    exit(0)

                if command.lower() == "clear":
                    print('\033c', end='')

                # command_history.append(command)
                # while len(command_history) > command_history_max:
                #     command_history.pop(0)

                else:
                    code = execute(
                        configdir = args.config,
                        identitypath = args.identity,
                        verbosity = args.verbose,
                        quietness = args.quiet,
                        detailed = args.detailed,
                        mirror = args.mirror,
                        noid = args.noid,
                        destination = args.destination,
                        command = command,
                        stdin = None,
                        stdoutl = args.stdout,
                        stderrl = args.stderr,
                        timeout = args.w,
                        result_timeout = args.W,
                        interactive = True,
                    )

        else:
            print("")
            parser.print_help()
            print("")

    except KeyboardInterrupt:
        # tty.setnocbreak(sys.stdin.fileno())
        print("")
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

def pretty_time(time, verbose=False):
    days = int(time // (24 * 3600))
    time = time % (24 * 3600)
    hours = int(time // 3600)
    time %= 3600
    minutes = int(time // 60)
    time %= 60
    seconds = round(time, 2)
    
    ss = "" if seconds == 1 else "s"
    sm = "" if minutes == 1 else "s"
    sh = "" if hours == 1 else "s"
    sd = "" if days == 1 else "s"

    components = []
    if days > 0:
        components.append(str(days)+" day"+sd if verbose else str(days)+"d")

    if hours > 0:
        components.append(str(hours)+" hour"+sh if verbose else str(hours)+"h")

    if minutes > 0:
        components.append(str(minutes)+" minute"+sm if verbose else str(minutes)+"m")

    if seconds > 0:
        components.append(str(seconds)+" second"+ss if verbose else str(seconds)+"s")

    i = 0
    tstr = ""
    for c in components:
        i += 1
        if i == 1:
            pass
        elif i < len(components):
            tstr += ", "
        elif i == len(components):
            tstr += " and "

        tstr += c

    return tstr

if __name__ == "__main__":
    main()
