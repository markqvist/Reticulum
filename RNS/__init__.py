# Reticulum License
#
# Copyright (c) 2016-2026 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
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
import datetime
import random
import threading
import math
import bisect

from ._version import __version__
from collections import deque
from functools import partial, wraps
from RNS.Stamps import quantize_cost

py_modules  = glob.glob(os.path.dirname(__file__)+"/*.py")
pyc_modules = glob.glob(os.path.dirname(__file__)+"/*.pyc")
so_modules  = glob.glob(os.path.dirname(__file__)+"/*.so")
pyd_modules = glob.glob(os.path.dirname(__file__)+"/*.pyd")
modules     = py_modules+pyc_modules+so_modules+pyd_modules
__all__ = list(set([os.path.basename(f).split(".")[0] for f in modules if not os.path.basename(f).split(".")[0] == "__init__"]))

import importlib.util
try: from ._buildinfo import compiled
except ImportError:
    if importlib.util.find_spec("cython"): import cython; compiled = cython.compiled
    else: compiled = False

LOG_NONE     = -1
LOG_CRITICAL = 0
LOG_ERROR    = 1
LOG_WARNING  = 2
LOG_NOTICE   = 3
LOG_INFO     = 4
LOG_VERBOSE  = 5
LOG_DEBUG    = 6
LOG_PATHING  = 7
LOG_EXTREME  = 8

LOG_STDOUT   = 0x91
LOG_FILE     = 0x92
LOG_CALLBACK = 0x93

LOG_MAXSIZE  = 5*1024*1024

loglevel        = LOG_NOTICE
logfile         = None
logdest         = LOG_STDOUT
logcall         = None
logtimestamps   = True
logtimefmt      = "%Y-%m-%d %H:%M:%S"
logtimefmt_p    = "%H:%M:%S.%f"
compact_log_fmt = False

instance_random = random.Random()
instance_random.seed(os.urandom(10))

_always_override_destination = False

logging_lock = threading.Lock()

def loglevelname(level):
    if (level == LOG_CRITICAL): return "[Critical]"
    if (level == LOG_ERROR):    return "[Error]   "
    if (level == LOG_WARNING):  return "[Warning] "
    if (level == LOG_NOTICE):   return "[Notice]  "
    if (level == LOG_INFO):     return "[Info]    "
    if (level == LOG_VERBOSE):  return "[Verbose] "
    if (level == LOG_DEBUG):    return "[Debug]   "
    if (level == LOG_PATHING):  return "[Pathing] "
    if (level == LOG_EXTREME):  return "[Extra]   "
    
    return "Unknown"

def version():
    return __version__

def host_os():
    from .vendor.platformutils import get_platform
    return get_platform()

def timestamp_str(time_s):
    timestamp = time.localtime(time_s)
    return time.strftime(logtimefmt, timestamp)

def precise_timestamp_str(time_s):
    return datetime.datetime.now().strftime(logtimefmt_p)[:-3]

def sl(level=3): return loglevel >= level
def log(msg, level=3, _override_destination = False, pt=False):
    if loglevel == LOG_NONE: return
    global _always_override_destination, compact_log_fmt
    msg = str(msg)
    if loglevel >= level:
        if pt: logstring = "["+precise_timestamp_str(time.time())+"] "+loglevelname(level)+" "+msg
        else:
            if not compact_log_fmt: logstring = ("["+timestamp_str(time.time())+"] " if logtimestamps else "")+loglevelname(level)+" "+msg
            else:                   logstring = ("["+timestamp_str(time.time())+"] " if logtimestamps else "")+msg

        with logging_lock:
            if (logdest == LOG_STDOUT or _always_override_destination or _override_destination):
                if not threading.main_thread().is_alive(): return
                else:
                    try: print(logstring)
                    except: pass

            elif (logdest == LOG_FILE and logfile != None):
                try:
                    with open(logfile, "a") as file: file.write(logstring+"\n")
                    if os.path.getsize(logfile) > LOG_MAXSIZE:
                        prevfile = logfile+".1"
                        if os.path.isfile(prevfile): os.unlink(prevfile)
                        os.rename(logfile, prevfile)

                except Exception as e:
                    _always_override_destination = True
                    log("Exception occurred while writing log message to log file: "+str(e), LOG_CRITICAL)
                    log("Dumping future log events to console!", LOG_CRITICAL)
                    log(msg, level)

            elif logdest == LOG_CALLBACK:
                try: logcall(logstring)
                except Exception as e:
                    _always_override_destination = True
                    log("Exception occurred while calling external log handler: "+str(e), LOG_CRITICAL)
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
    try: iter(data)
    except TypeError: data = [data]
        
    delimiter = ":"
    if not delimit: delimiter = ""
    hexrep = delimiter.join("{:02x}".format(c) for c in data)
    return hexrep

def prettyhexrep(data):
    delimiter = ""
    hexrep = "<"+delimiter.join("{:02x}".format(c) for c in data)+">"
    return hexrep

def prettycost(value):
    if value == None: return "?"
    elif not type(value) in (float, int): return "?"
    else: return f"{quantize_cost(value):.3f}"

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
            if unit == "": return "%.0f %s%s" % (num, unit, suffix)
            else:          return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

def prettyfrequency(hz, suffix="Hz", d=2, lpf=False):
    if hz == 0: return "0 Hz"
    if not lpf: num = hz*1e6
    else:       num = hz
    if not lpf: units = ["µ", "m", "", "K","M","G","T","P","E","Z"]
    else:       units = ["", "K","M","G","T","P","E","Z"]
    last_unit = "Y"

    for unit in units:
        if abs(num) < 1000.0:
            if d == 2: return "%.2f %s%s" % (num, unit, suffix)
            else:      return "%s %s%s" % (str(round(num,d)), unit, suffix)
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

        if abs(num) < divisor: return "%.2f %s%s" % (num, unit, suffix)
        num /= divisor

    return "%.2f %s%s" % (num, last_unit, suffix)

def prettytime(time, verbose=False, compact=False):
    neg = False
    if time < 0:
        time = abs(time)
        neg = True

    days = int(time // (24 * 3600))
    time = time % (24 * 3600)
    hours = int(time // 3600)
    time %= 3600
    minutes = int(time // 60)
    time %= 60
    if compact: seconds = int(time)
    else:       seconds = round(time, 2)
    
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
        if   i == 1: pass
        elif i <  len(components): tstr += ", "
        elif i == len(components): tstr += " and "

        tstr += c

    if tstr == "": return "0s"
    else:
        if not neg: return tstr
        else: return f"-{tstr}"

def prettyshorttime(time, verbose=False, compact=False, tight=False):
    neg = False
    time = time*1e6
    if time < 0:
        time = abs(time)
        neg = True
    
    seconds = int(time // 1e6); time %= 1e6
    milliseconds = int(time // 1e3); time %= 1e3

    if compact: microseconds = int(time)
    else:       microseconds = round(time, 2)
    
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
        if   i == 1: pass
        elif i <  len(components): tstr += ", " if not tight else " "
        elif i == len(components): tstr += " and " if not tight else " "

        tstr += c

    if tstr == "": return "0us"
    else:
        if not neg: return tstr
        else:       return f"-{tstr}"

def phyparams():
    print("Required Physical Layer MTU : "+str(Reticulum.MTU)+" bytes")
    print("Plaintext Packet MDU        : "+str(Packet.PLAIN_MDU)+" bytes")
    print("Encrypted Packet MDU        : "+str(Packet.ENCRYPTED_MDU)+" bytes")
    print("Link Curve                  : "+str(Link.CURVE))
    print("Link Packet MDU             : "+str(Link.MDU)+" bytes")
    print("Link Public Key Size        : "+str(Link.ECPUBSIZE*8)+" bits")
    print("Link Private Key Size       : "+str(Link.KEYSIZE*8)+" bits")

def panic(): os._exit(255)

exit_called = False
def exit(code=0):
    global exit_called
    if not exit_called:
        exit_called = True
        Reticulum.exit_handler()
        os._exit(code)

def _detach_stdout():
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

class Profiler:
    _ran = False
    profilers = {}
    tags = {}

    # Samples per tag
    MAX_CAPTURES = 10000

    @staticmethod
    def get_profiler(tag=None, super_tag=None, max_captures=None):
        if tag in Profiler.profilers: return Profiler.profilers[tag]
        else:
            if max_captures is None: max_captures = Profiler.MAX_CAPTURES
            profiler = Profiler(tag, super_tag, max_captures)
            Profiler.profilers[tag] = profiler
            return profiler

    @staticmethod
    def profile(func=None, *, tag=None, max_captures=None):
        """
        Decorator to profile a function. With no arguments, it can be
        used as `@RNS.Profiler.profile`, in which case it will use the
        qualified name of the function as the profiler tag. It can
        also be used as `@RNS.Profiler.profile(tag="prof_tag")` to use
        a specific profiler tag.

        :param tag: Either a profiler tag as passed to `Profiler.get_profiler(...)` or a `Profiler` object.
        :param max_captures: Maximum samples to capture for the specified profiler tag.
        """
        if func is None:
            return partial(Profiler.profile, tag=tag, max_captures=max_captures)

        tag = func.__qualname__ if tag is None else tag
        if isinstance(tag, Profiler): profiler = tag
        else:                         profiler = Profiler.get_profiler(tag=tag, max_captures=max_captures)

        @wraps(func)
        def wrapper(*args, **kwargs):
            with profiler:
                return func(*args, **kwargs)
        return wrapper

    def __init__(self, tag=None, super_tag=None, max_captures=None):
        self.paused = False
        self.pause_time = 0
        self.pause_started = None
        self.tag = tag
        self.super_tag = super_tag
        self.max_captures = max_captures if max_captures is not None else Profiler.MAX_CAPTURES

        if self.super_tag in Profiler.profilers:
            self.super_profiler = Profiler.profilers[self.super_tag]
            self.pause_super = self.super_profiler.pause
            self.resume_super = self.super_profiler.resume

        else:
            def noop(self=None): pass
            self.super_profiler = None
            self.pause_super = noop
            self.resume_super = noop

    def __enter__(self):
        self.pause_super()
        tag = self.tag
        super_tag = self.super_tag
        thread_ident = threading.get_ident()
        if not tag in Profiler.tags: Profiler.tags[tag] = {"threads": {}, "super": super_tag, "captures": deque(maxlen=self.max_captures)}
        if not thread_ident in Profiler.tags[tag]["threads"]:
            Profiler.tags[tag]["threads"][thread_ident] = {"running": deque()}

        # The tag deque stores a shared reference to the capture, and the end
        # time isn't updated until the context manager exits. This leaves the
        # deque sorted by start time, except for cases where the thread is
        # preemted between getting the current time and appending. We also store
        # a stack of start times per thread to support reentrancy.
        capture = {"start": time.perf_counter(), "end": None, "thread_ident": thread_ident}
        Profiler.tags[tag]["captures"].append(capture)
        Profiler.tags[tag]["threads"][thread_ident]["running"].append(capture)
        self.resume_super()

    def __exit__(self, exc_type, exc_value, traceback):
        self.pause_super()
        tag = self.tag
        super_tag = self.super_tag
        end = time.perf_counter() - self.pause_time
        self.pause_time = 0
        thread_ident = threading.get_ident()
        try:
            if tag in Profiler.tags and thread_ident in Profiler.tags[tag]["threads"]:
                try: capture = Profiler.tags[tag]["threads"][thread_ident]["running"].pop()
                except IndexError as e: return
                capture["end"] = end
                if not Profiler._ran:
                    Profiler._ran = True
        finally:
            self.resume_super()

    def pause(self, pause_started=None):
        if not self.paused:
            self.paused = True
            self.pause_started = pause_started or time.perf_counter()
            self.pause_super(self.pause_started)

    def resume(self):
        if self.paused:
            self.pause_time += time.perf_counter() - self.pause_started
            self.paused = False
            self.resume_super()

    @staticmethod
    def ran(): return Profiler._ran

    @staticmethod
    def results():
        def find_window_start(captures, start_time, hi=None):
            hi = len(captures) if hi is None else hi
            idx = bisect.bisect_left(captures, start_time, hi=hi, key=lambda c: c["start"])
            return idx if len(captures) - idx > 1 else None

        # Fast one-pass calculation of summary statistics
        def calc_stats(captures, start=0, end=None, key=lambda c: c, threads_key=None):
            if end is None: end = len(captures)
            while start > 0 and start <  len(captures) and start < end and key(captures[start]) is None: start += 1
            while   end > 0 and   end <= len(captures) and start < end and key(captures[end-1]) is None:   end -= 1
            count = end - start

            if count <= 0: return None
            elif count == 1:
                capture = key(captures[start])
                return { "count":   1,
                         "mean":    capture,
                         "median":  capture,
                         "min":     capture,
                         "max":     capture,
                         "stdev":   None,
                         "sum":     capture,
                         "threads": 1 if threads_key else None}

            # Median is approximate if there are any incomplete captures in the
            # middle of the range.
            med_even = count % 2 == 0
            med_idx  = start + (count // 2 if med_even else (count - 1) // 2)
            while key(captures[med_idx]) is None and med_idx < end: med_idx += 1
            if med_idx == end: c_median = None
            elif med_even:     c_median = key(captures[med_idx])
            else:
                med_idx2 = med_idx + 1
                while key(captures[med_idx2]) is None and med_idx2 < end: med_idx2 += 1
                if med_idx2 == end: c_median = None
                else:
                    med_cap1 = key(captures[med_idx])
                    med_cap2 = key(captures[med_idx+1])
                    if med_cap1 is None or med_cap2 is None: c_median = None
                    else:                                    c_median = (med_cap1 + med_cap2) / 2

            c_count = 0; c_sum = 0; c_min = key(captures[start]); c_max = key(captures[start]); ck = 0; ck2 = 0
            uniq_threads = set()
            for idx in range(start, end):
                c = key(captures[idx])
                if c is None: continue
                else:         c_count += 1
                c_sum += c
                if c < c_min: c_min = c
                if c > c_max: c_max = c
                ck  += c - c_median
                ck2 += (c - c_median) ** 2
                if threads_key: uniq_threads.add(threads_key(captures[idx]))
            c_mean = c_sum / c_count if c_count > 0 else None
            c_std = math.sqrt((ck2 - (ck ** 2)/c_count) / (c_count - 1)) if c_count > 1 else None

            return { "count":   c_count,
                     "mean":    c_mean,
                     "median":  c_median,
                     "min":     c_min,
                     "max":     c_max,
                     "stdev":   c_std,
                     "sum":     c_sum,
                     "threads": len(uniq_threads) if threads_key else None }

        def stats_key(capture):
            end = capture["end"]
            if end is None: return None
            else:           return end - capture["start"]

        results = {}
        now = time.perf_counter()
        for tag in sorted(Profiler.tags):
            tag_entry = Profiler.tags[tag]
            tag_captures = sorted(tag_entry["captures"], key=lambda c: c["start"])

            if len(tag_captures):
                captures_1m = None; captures_5m = None; captures_30m = None; captures_60m = None
                stats_1m = None; stats_5m = None; stats_30m = None; stats_60m = None

                captures_1m = find_window_start(tag_captures, now - 1*60)
                if captures_1m:  captures_5m  = find_window_start(tag_captures, now - 5*60, hi=captures_1m)
                if captures_5m:  captures_30m = find_window_start(tag_captures, now - 30*60, hi=captures_5m)
                if captures_30m: captures_60m = find_window_start(tag_captures, now - 60*60, hi=captures_30m)

                stats_all                  = calc_stats(tag_captures, 0,            None,         key=stats_key, threads_key=lambda c: c["thread_ident"])
                if captures_1m:  stats_1m  = calc_stats(tag_captures, captures_1m,  None,         key=stats_key)
                if captures_5m:  stats_5m  = calc_stats(tag_captures, captures_5m,  captures_1m,  key=stats_key)
                if captures_30m: stats_30m = calc_stats(tag_captures, captures_30m, captures_5m,  key=stats_key)
                if captures_60m: stats_60m = calc_stats(tag_captures, captures_60m, captures_30m, key=stats_key)

                if stats_all["count"]:
                    results[tag] = { "name":      tag,
                                     "super":     tag_entry["super"],
                                     "stats_all": stats_all,
                                     "stats_1m":  stats_1m,
                                     "stats_5m":  stats_5m,
                                     "stats_30m": stats_30m,
                                     "stats_60m": stats_60m }

            # Yield to avoid bogging down the instance
            time.sleep(0.001)

        return results

    @staticmethod
    def format_results(results):
        def pst(time):
            if time is not None: return prettyshorttime(time, tight=True)
            else:                return "-----"

        def print_results_recursive(tag, results, level=0):
            results_str = print_tag_results(tag, level+1) + "\n"

            for tag_name in results:
                sub_tag = results[tag_name]
                if sub_tag["super"] == tag["name"]:
                    results_str += print_results_recursive(sub_tag, results, level=level+1)

            return results_str

        def print_tag_results(tag, level):
            ind = "  "*level
            name = tag["name"]
            stats_all = tag["stats_all"]; stats_1m = tag["stats_1m"]; stats_5m = tag["stats_5m"]; stats_30m = tag["stats_30m"]; stats_60m = tag["stats_60m"]
            results_str  =     f" {ind}{name}\n"
            results_str +=     f" {ind}  Samples  : {stats_all['count']} from {stats_all['threads']} thread{'s' if stats_all['threads'] > 1 else ''}\n"
            if stats_all != None:
                results_str += f" {ind}              {'Mean':^15} | {'Median':^15} | {'Min':^15} | {'Max':^15} | {'St. dev':^15} | {'Total':^15}\n"
                results_str += f" {ind}  Stats    : ({pst(stats_all['mean']):^15} | {pst(stats_all['median']):^15} | {pst(stats_all['min']):^15} | {pst(stats_all['max']):^15} | {pst(stats_all['stdev']):^15} | {pst(stats_all['sum']):^15})\n"
            if stats_1m != None:
                results_str += f" {ind}   0-1m    : ({pst(stats_1m['mean']):^15} | {pst(stats_1m['median']):^15} | {pst(stats_1m['min']):^15} | {pst(stats_1m['max']):^15} | {pst(stats_1m['stdev']):^15} | {pst(stats_1m['sum']):^15})\n"
            if stats_5m != None:
                results_str += f" {ind}   1-5m    : ({pst(stats_5m['mean']):^15} | {pst(stats_5m['median']):^15} | {pst(stats_5m['min']):^15} | {pst(stats_5m['max']):^15} | {pst(stats_5m['stdev']):^15} | {pst(stats_5m['sum']):^15})\n"
            if stats_30m != None:
                results_str += f" {ind}  5-30m    : ({pst(stats_30m['mean']):^15} | {pst(stats_30m['median']):^15} | {pst(stats_30m['min']):^15} | {pst(stats_30m['max']):^15} | {pst(stats_30m['stdev']):^15} | {pst(stats_30m['sum']):^15})\n"
            if stats_60m != None:
                results_str += f" {ind} 30-60m    : ({pst(stats_60m['mean']):^15} | {pst(stats_60m['median']):^15} | {pst(stats_60m['min']):^15} | {pst(stats_60m['max']):^15} | {pst(stats_60m['stdev']):^15} | {pst(stats_60m['sum']):^15})\n"
            return results_str

        results_str = ""
        for tag_name in results:
            tag = results[tag_name]
            if tag["super"] == None:
                results_str += print_results_recursive(tag, results)

        return results_str

profile = Profiler.get_profiler

# The base-256 table is likely to change. Currently, it is just
# experimental, so don't count on it too much just yet.
b256 = [
# 0   1   2   3   4   5   6   7   8   9   A   B   C   D   F   F
 "a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p",  # 0x0 Latin & numerals
 "q","r","s","t","u","v","x","y","z","æ","ø","0","1","2","3","4",  # 0x1 Latin & numerals
 "A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P",  # 0x2 Latin & numerals
 "Q","R","S","T","U","W","X","Y","Z","Æ","Ø","5","6","7","8","9",  # 0x3 Latin & numerals
 "α","β","γ","δ","ε","ζ","η","θ","ι","κ","λ","μ","ν","ξ","π","ρ",  # 0x4 Greek
 "σ","τ","φ","χ","ψ","ω","Γ","Δ","Θ","Λ","Ξ","Π","Σ","Φ","Ψ","Ω",  # 0x5 Greek
 "Б","Д","Ж","З","И","Л","П","Ц","Ч","Ш","Щ","Ъ","Ы","Э","Ю","Я",  # 0x6 Cyrillic
 "б","д","ж","з","и","л","п","ц","ч","ш","щ","ъ","ы","э","ю","я",  # 0x7 Cyrillic
 "Ա","Բ","Գ","Դ","Ե","Զ","Է","Ը","Թ","Ժ","Ի","Խ","Ծ","Կ","Հ","Ձ",  # 0x8 Armenian Capitals
 "Ղ","Ճ","Մ","Յ","Ն","Շ","Ո","Չ","Պ","Ջ","Վ","Ր","Ց","Ւ","Ք","Ֆ",  # 0x9 Armenian Captials
 "ᚠ","ᚢ","ᚦ","ᚱ","ᚹ","ᚺ","ᚾ","ᛈ","ᛇ","ᛉ","ᛊ","ᛏ","ᛒ","ᛖ","ᛗ","ᛟ",   # 0xA Elder Futhark
 "ｲ","ｳ","ｵ","ｶ","ｷ","ｹ","ｻ","ｼ","ｽ","ｾ","ﾀ","ﾁ","ﾃ","ﾄ","ﾅ","ﾇ",     # 0xB Katakana
 "ﾈ","ﾋ","ﾌ","ﾍ","ﾎ","ﾏ","ﾐ","ﾑ","ﾒ","ﾓ","ﾔ","ﾗ","ﾘ","ﾙ","ﾚ","ﾜ",     # 0xC Katakana
 "𐑐","𐑑","𐑒","𐑔","𐑕","𐑗","𐑙","𐑳","𐑶","𐑸","𐑹","𐑺","𐑻","𐑽","𐑾","𐑿",    # 0xD Shavian
 "᱑","᱕","᱘","᱙","ᱚ","ᱝ","ᱟ","ᱣ","ᱦ","ᱨ","ᱬ","ᱭ","ᱰ","ᱳ","ᱶ","ᱷ", # 0xE Ol Chiki
 "𐌳","𐌸","𐌾","𐐀","𐐁","𐐂","𐐆","𐐇","𐐈","𐐉","𐐊","𐐋","𐐌","𐐍","𐐎","𐐏", # 0xF Gothic & Deseret
]

def b256rep(data):       return "".join(bytes_to_b256(data))
def prettyb256rep(data): return f"<{b256rep(data)}>"

def b256_to_byte(point):
    if not type(point) == str or not len(point) == 1: raise TypeError("Invalid input data for base256 byte decode")
    try: return b256.index(point)
    except Exception as e: raise ValueError(f"Could not decode base256 byte: {e}")

def b256_to_bytes(b256rep):
    if not type(b256rep) == str: raise TypeError("Invalid input data for base256 decode")
    try: return bytes([b256.index(c) for c in b256rep])
    except Exception as e: raise ValueError(f"Could not decode base256: {e}")

def byte_to_b256(input_byte):
    if type(input_byte) == bytes and not len(input_byte) == 1: TypeError("Invalid input data for base256 byte encode")
    if type(input_byte) == bytes and len(input_byte) == 1: input_byte = ord(input_byte)
    if not type(input_byte) == int: raise TypeError("Invalid input data for base256 byte encode")
    try: return b256[int(input_byte)]
    except Exception as e: raise TypeError(f"Could not encode byte to base256: {e}")

def bytes_to_b256(data):
    if not type(data) == bytes: raise TypeError("Invalid input data for base256 encode")
    try: return [byte_to_b256(c) for c in data]
    except Exception as e: raise TypeError(f"Could not encode to base256: {e}")


from .Reticulum import Reticulum
from .Identity import Identity
from .Link import Link, RequestReceipt
from .Channel import MessageBase
from .Buffer import Buffer, RawChannelReader, RawChannelWriter
from .Transport import Transport
from .Discovery import InterfaceAnnouncer
from .Destination import Destination
from .Packet import Packet
from .Packet import PacketReceipt
from .Resolver import Resolver
from .Resource import Resource, ResourceAdvertisement
from .Cryptography import HKDF
from .Cryptography import Hashes