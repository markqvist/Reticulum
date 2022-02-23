import socket
import os
import random
import string

from . import sam

def get_free_port():
    """Get a free port on your local host"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 0))
    free_port = s.getsockname()[1]
    s.close()
    return free_port

def is_address_accessible(address):
    """Check if address is accessible or down"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_accessible = s.connect_ex(address) == 0
    s.close()
    return is_accessible

def address_from_string(address_string):
    """Address tuple from host:port string"""
    address = address_string.split(":")
    return (address[0], int(address[1]))

def get_sam_address():
    """
    Get SAM address from environment variable I2P_SAM_ADDRESS, or use a default
    value
    """
    value = os.getenv("I2P_SAM_ADDRESS")
    return address_from_string(value) if value else sam.DEFAULT_ADDRESS

def generate_session_id(length=6):
    """Generate random session id"""
    rand = random.SystemRandom()
    sid = [rand.choice(string.ascii_letters) for _ in range(length)]
    return "reticulum-" + "".join(sid)

