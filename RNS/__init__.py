# MIT License
#
# Copyright (c) 2016-2023 Mark Qvist / unsigned.io and contributors
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

import os
import sys
import glob
import time
import random
import threading

from ._version import __version__

from .Reticulum import Reticulum
from .Identity import Identity
from .Link import Link, RequestReceipt
from .Channel import MessageBase
from .Buffer import Buffer, RawChannelReader, RawChannelWriter
from .Transport import Transport
from .Destination import Destination
from .Packet import Packet
from .Packet import PacketReceipt
from .Resolver import Resolver
from .Resource import Resource, ResourceAdvertisement
from .Cryptography import HKDF
from .Cryptography import Hashes

modules = glob.glob(os.path.dirname(__file__)+"/*.py")
__all__ = [ os.path.basename(f)[:-3] for f in modules if not f.endswith('__init__.py')]

LOG_CRITICAL = 0
LOG_ERROR    = 1
LOG_WARNING  = 2
LOG_NOTICE   = 3
LOG_INFO     = 4
LOG_VERBOSE  = 5
LOG_DEBUG    = 6
LOG_EXTREME  = 7

LOG_STDOUT   = 0x91
LOG_FILE     = 0x92

LOG_MAXSIZE  = 5*1024*1024

loglevel        = LOG_NOTICE
logfile         = None
logdest         = LOG_STDOUT
logtimefmt      = "%Y-%m-%d %H:%M:%S"
compact_log_fmt = False

instance_random = random.Random()
instance_random.seed(os.urandom(10))

_always_override_destination = False

logging_lock = threading.Lock()

def loglevelname(level):
    if (level == LOG_CRITICAL):
        return "Critical"
    if (level == LOG_ERROR):
        return "Error"
    if (level == LOG_WARNING):
        return "Warning"
    if (level == LOG_NOTICE):
        return "Notice"
    if (level == LOG_INFO):
        return "Info"
    if (level == LOG_VERBOSE):
        return "Verbose"
    if (level == LOG_DEBUG):
        return "Debug"
    if (level == LOG_EXTREME):
        return "Extra"
    
    return "Unknown"

def version():
    return __version__

def host_os():
    from .vendor.platformutils import get_platform
    return get_platform()

def timestamp_str(time_s):
    timestamp = time.localtime(time_s)
    return time.strftime(logtimefmt, timestamp)

def log(msg, level=3, _override_destination = False):
    global _always_override_destination, compact_log_fmt
    msg = str(msg)
    if loglevel >= level:
        if not compact_log_fmt:
            logstring = "["+timestamp_str(time.time())+"] ["+loglevelname(level)+"] "+msg
        else:
            logstring = "["+timestamp_str(time.time())+"] "+msg

        logging_lock.acquire()

        if (logdest == LOG_STDOUT or _always_override_destination or _override_destination):
            print(logstring)
            logging_lock.release()

        elif (logdest == LOG_FILE and logfile != None):
            try:
                file = open(logfile, "a")
                file.write(logstring+"\n")
                file.close()
                
                if os.path.getsize(logfile) > LOG_MAXSIZE:
                    prevfile = logfile+".1"
                    if os.path.isfile(prevfile):
                        os.unlink(prevfile)
                    os.rename(logfile, prevfile)

                logging_lock.release()
            except Exception as e:
                logging_lock.release()
                _always_override_destination = True
                log("Exception occurred while writing log message to log file: "+str(e), LOG_CRITICAL)
                log("Dumping future log events to console!", LOG_CRITICAL)
                log(msg, level)
                

def rand():
    result = instance_random.random()
    return result

def trace_exception(e):
    import traceback
    exception_info = "".join(traceback.TracebackException.from_exception(e).format())
    log(f"An unhandled {str(type(e))} exception occurred: {str(e)}", LOG_ERROR)
    log(exception_info, LOG_ERROR)

def hexrep(data, delimit=True):
    try:
        iter(data)
    except TypeError:
        data = [data]
        
    delimiter = ":"
    if not delimit:
        delimiter = ""
    hexrep = delimiter.join("{:02x}".format(c) for c in data)
    return hexrep

def prettyhexrep(data):
    delimiter = ""
    hexrep = "<"+delimiter.join("{:02x}".format(c) for c in data)+">"
    return hexrep

def prettyspeed(num, suffix="b"):
    return prettysize(num/8, suffix=suffix)+"ps"

def prettysize(num, suffix='B'):
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

def prettyfrequency(hz, suffix="Hz"):
    num = hz*1e6
    units = ["µ", "m", "", "K","M","G","T","P","E","Z"]
    last_unit = "Y"

    for unit in units:
        if abs(num) < 1000.0:
            return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

def prettydistance(m, suffix="m"):
    num = m*1e6
    units = ["µ", "m", "c", ""]
    last_unit = "K"

    for unit in units:
        divisor = 1000.0
        if unit == "m": divisor = 10
        if unit == "c": divisor = 100

        if abs(num) < divisor:
            return "%.2f %s%s" % (num, unit, suffix)
        num /= divisor

    return "%.2f %s%s" % (num, last_unit, suffix)

def prettytime(time, verbose=False, compact=False):
    days = int(time // (24 * 3600))
    time = time % (24 * 3600)
    hours = int(time // 3600)
    time %= 3600
    minutes = int(time // 60)
    time %= 60
    if compact:
        seconds = int(time)
    else:
        seconds = round(time, 2)
    
    ss = "" if seconds == 1 else "s"
    sm = "" if minutes == 1 else "s"
    sh = "" if hours == 1 else "s"
    sd = "" if days == 1 else "s"

    displayed = 0
    components = []
    if days > 0 and ((not compact) or displayed < 2):
        components.append(str(days)+" day"+sd if verbose else str(days)+"d")
        displayed += 1

    if hours > 0 and ((not compact) or displayed < 2):
        components.append(str(hours)+" hour"+sh if verbose else str(hours)+"h")
        displayed += 1

    if minutes > 0 and ((not compact) or displayed < 2):
        components.append(str(minutes)+" minute"+sm if verbose else str(minutes)+"m")
        displayed += 1

    if seconds > 0 and ((not compact) or displayed < 2):
        components.append(str(seconds)+" second"+ss if verbose else str(seconds)+"s")
        displayed += 1

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

    if tstr == "":
        return "0s"
    else:
        return tstr

def prettyshorttime(time, verbose=False, compact=False):
    time = time*1e6
    
    seconds = int(time // 1e6); time %= 1e6
    milliseconds = int(time // 1e3); time %= 1e3

    if compact:
        microseconds = int(time)
    else:
        microseconds = round(time, 2)
    
    ss = "" if seconds == 1 else "s"
    sms = "" if milliseconds == 1 else "s"
    sus = "" if microseconds == 1 else "s"

    displayed = 0
    components = []
    if seconds > 0 and ((not compact) or displayed < 2):
        components.append(str(seconds)+" second"+ss if verbose else str(seconds)+"s")
        displayed += 1

    if milliseconds > 0 and ((not compact) or displayed < 2):
        components.append(str(milliseconds)+" millisecond"+sms if verbose else str(milliseconds)+"ms")
        displayed += 1

    if microseconds > 0 and ((not compact) or displayed < 2):
        components.append(str(microseconds)+" microsecond"+sus if verbose else str(microseconds)+"µs")
        displayed += 1

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

    if tstr == "":
        return "0us"
    else:
        return tstr

def phyparams():
    print("Required Physical Layer MTU : "+str(Reticulum.MTU)+" bytes")
    print("Plaintext Packet MDU        : "+str(Packet.PLAIN_MDU)+" bytes")
    print("Encrypted Packet MDU        : "+str(Packet.ENCRYPTED_MDU)+" bytes")
    print("Link Curve                  : "+str(Link.CURVE))
    print("Link Packet MDU             : "+str(Link.MDU)+" bytes")
    print("Link Public Key Size        : "+str(Link.ECPUBSIZE*8)+" bits")
    print("Link Private Key Size       : "+str(Link.KEYSIZE*8)+" bits")

def panic():
    os._exit(255)

def exit():
    print("")
    sys.exit(0)


profiler_ran = False
profiler_tags = {}
def profiler(tag=None, capture=False, super_tag=None):
    global profiler_ran, profiler_tags
    try:
        thread_ident = threading.get_ident()

        if capture:
            end = time.perf_counter()
            if tag in profiler_tags and thread_ident in profiler_tags[tag]["threads"]:
                if profiler_tags[tag]["threads"][thread_ident]["current_start"] != None:
                    begin = profiler_tags[tag]["threads"][thread_ident]["current_start"]
                    profiler_tags[tag]["threads"][thread_ident]["current_start"] = None
                    profiler_tags[tag]["threads"][thread_ident]["captures"].append(end-begin)
                    if not profiler_ran:
                        profiler_ran = True

        else:
            if not tag in profiler_tags:
                profiler_tags[tag] = {"threads": {}, "super": super_tag}
            if not thread_ident in profiler_tags[tag]["threads"]:
                profiler_tags[tag]["threads"][thread_ident] = {"current_start": None, "captures": []}

            profiler_tags[tag]["threads"][thread_ident]["current_start"] = time.perf_counter()

    except Exception as e:
        trace_exception(e)

def profiler_results():
    from statistics import mean, median, stdev
    results = {}
    
    for tag in profiler_tags:
        tag_captures = []
        tag_entry = profiler_tags[tag]
        
        for thread_ident in tag_entry["threads"]:
            thread_entry = tag_entry["threads"][thread_ident]
            thread_captures = thread_entry["captures"]
            sample_count = len(thread_captures)
            
            if sample_count > 2:
                thread_results = {
                    "count": sample_count,
                    "mean": mean(thread_captures),
                    "median": median(thread_captures),
                    "stdev": stdev(thread_captures)
                }

            tag_captures.extend(thread_captures)

        sample_count = len(tag_captures)
        if sample_count > 2:
            tag_results = {
                "name": tag,
                "super": tag_entry["super"],
                "count": len(tag_captures),
                "mean": mean(tag_captures),
                "median": median(tag_captures),
                "stdev": stdev(tag_captures)
            }

            results[tag] = tag_results

    def print_results_recursive(tag, results, level=0):
        print_tag_results(tag, level+1)

        for tag_name in results:
            sub_tag = results[tag_name]
            if sub_tag["super"] == tag["name"]:
                print_results_recursive(sub_tag, results, level=level+1)


    def print_tag_results(tag, level):
        ind = "  "*level
        name = tag["name"]; count = tag["count"]
        mean = tag["mean"]; tag["median"]; stdev = tag["stdev"]
        print(f"{ind}{name}")
        print(f"{ind}  Samples : {count}")
        print(f"{ind}  Mean    : {prettyshorttime(mean)}")
        print(f"{ind}  Median  : {prettyshorttime(median)}")
        print(f"{ind}  St.dev. : {prettyshorttime(stdev)}")
        print("")

    print("\nProfiler results:\n")
    for tag_name in results:
        tag = results[tag_name]
        if tag["super"] == None:
            print_results_recursive(tag, results)
