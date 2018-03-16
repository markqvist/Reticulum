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

# d2=Destination(identity, Destination.IN, Destination.PLAIN, "plainchat", "markqvist")
# d2.setCallback(testCallback)

print identity.hexhash
print d1.name
print d1.hexhash
print d1.identity.pub
print "---"
print

# p1=Packet(d1, "testmessage")
# p1.send()
msg=""
for x in range(300):
	msg += "a"
signed = d1.sign(msg)
sl = len(signed)
pl = len(d1.identity.pub_bytes)
print("Signature length is "+str(sl))
print("Minimum announce is "+str(pl+sl+8))


p2=Packet(d1, msg)
p2.send()

# p2=Packet(d2, "something else")
# p2.send()

raw_input()

