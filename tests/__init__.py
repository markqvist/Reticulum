compiling = False
noticed = False
notice_delay = 0.3
import time
import sys
import threading
from importlib.util import find_spec
if find_spec("pyximport") and find_spec("cython"):
    import pyximport; pyxloader = pyximport.install(pyimport=True, language_level=3)[1]

def notice_job():
    global noticed
    started = time.time()
    while compiling:
        if time.time() > started+notice_delay and compiling:
            noticed = True
            print("Compiling RNS object code... ", end="")
            sys.stdout.flush()
            break
        time.sleep(0.1)


compiling = True
threading.Thread(target=notice_job, daemon=True).start()
import RNS; compiling = False
if noticed: print("Done."); sys.stdout.flush()