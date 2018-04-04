# from RNS.Destination import *
# from RNS.Packet import *
# from RNS import Reticulum
from RNS import *
# from RNS import Destination
import os
import time

def testCallback(message, receiver):
  print("Got message from "+str(receiver)+": ")
  print(message)
  print("----------")


#RNS = Reticulum(configdir=os.path.expanduser("~")+"/.Reticulum2")
RNS = Reticulum()
identity = Identity()

d1=Destination(identity, Destination.IN, Destination.SINGLE, "messenger", "user")
#d1.setProofStrategy(Destination.PROVE_ALL)
d1.setCallback(testCallback)

msg=""
for x in range(300):
	msg += "a"
signed = d1.sign(msg)
sl = len(signed)
pl = len(d1.identity.pub_bytes)

d1.announce()
p1=Packet(d1, msg)
p1.send()

# p2=Packet(d2,"Test af msg")
# p2.send()

raw_input()