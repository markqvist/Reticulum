# from FPE.Destination import *
# from FPE.Packet import *
# from FPE import FlexPE
from FPE import *
# from FPE import Destination
import os
import time

def testCallback(message, receiver):
  print("Got message from "+str(receiver)+": ")
  print(message)
  print("----------")


#fpe = FlexPE(config=os.path.expanduser("~")+"/.flexpe/config.test")
fpe = FlexPE()
identity = Identity()

d1=Destination(identity, Destination.IN, Destination.SINGLE, "messenger", "user")
d1.setCallback(testCallback)

msg=""
for x in range(300):
	msg += "a"
signed = d1.sign(msg)
sl = len(signed)
pl = len(d1.identity.pub_bytes)

d1.announce()
p1=Packet(d1, msg)
#p1.send()

# p2=Packet(d2,"Test af msg")
# p2.send()

raw_input()