from base64 import b64decode, b64encode, b32encode
from hashlib import sha256
import struct
import re


I2P_B64_CHARS = "-~"

def i2p_b64encode(x):
    """Encode I2P destination"""
    return b64encode(x, altchars=I2P_B64_CHARS.encode()).decode() 

def i2p_b64decode(x):
    """Decode I2P destination"""
    return b64decode(x, altchars=I2P_B64_CHARS, validate=True)

SAM_BUFSIZE = 4096
DEFAULT_ADDRESS = ("127.0.0.1", 7656)
DEFAULT_MIN_VER = "3.1"
DEFAULT_MAX_VER = "3.1"
TRANSIENT_DESTINATION = "TRANSIENT"

VALID_BASE32_ADDRESS = re.compile(r"^([a-zA-Z0-9]{52}).b32.i2p$")
VALID_BASE64_ADDRESS = re.compile(r"^([a-zA-Z0-9-~=]{516,528})$")

class Message(object):
    """Parse SAM message to an object"""
    def __init__(self, s):
        self.opts = {}
        if type(s) != str:
            self._reply_string = s.decode().strip()
        else:
            self._reply_string = s

        self.cmd, self.action, opts = self._reply_string.split(" ", 2)
        for v in opts.split(" "):
            data = v.split("=", 1) if "=" in v else (v, True)
            self.opts[data[0]] = data[1]

    def __getitem__(self, key):
        return self.opts[key]

    @property
    def ok(self):
        return self["RESULT"] == "OK"

    def __repr__(self):
        return self._reply_string


# SAM request messages

def hello(min_version, max_version):
    return "HELLO VERSION MIN={} MAX={}\n".format(min_version, 
            max_version).encode()

def session_create(style, session_id, destination, options=""):
    return "SESSION CREATE STYLE={} ID={} DESTINATION={} {}\n".format(
            style, session_id, destination, options).encode()


def stream_connect(session_id, destination, silent="false"):
    return "STREAM CONNECT ID={} DESTINATION={} SILENT={}\n".format(
            session_id, destination, silent).encode()

def stream_accept(session_id, silent="false"):
    return "STREAM ACCEPT ID={} SILENT={}\n".format(session_id, silent).encode()

def stream_forward(session_id, port, options=""):
    return "STREAM FORWARD ID={} PORT={} {}\n".format(
            session_id, port, options).encode()



def naming_lookup(name):
    return "NAMING LOOKUP NAME={}\n".format(name).encode()

def dest_generate(signature_type):
    return "DEST GENERATE SIGNATURE_TYPE={}\n".format(signature_type).encode()

class Destination(object):
    """I2P destination

    https://geti2p.net/spec/common-structures#destination

    :param data: (optional) Base64 encoded data or binary data 
    :param path: (optional) A path to a file with binary data 
    :param has_private_key: (optional) Does data have a private key? 
    """

    ECDSA_SHA256_P256 = 1
    ECDSA_SHA384_P384 = 2
    ECDSA_SHA512_P521 = 3
    EdDSA_SHA512_Ed25519 = 7

    default_sig_type = EdDSA_SHA512_Ed25519

    _pubkey_size = 256
    _signkey_size = 128
    _min_cert_size = 3

    def __init__(self, data=None, path=None, has_private_key=False):
        #: Binary destination
        self.data = bytes() 
        #: Base64 encoded destination
        self.base64 = ""    
        #: :class:`RNS.vendor.i2plib.PrivateKey` instance or None
        self.private_key = None    
        
        if path:
            with open(path, "rb") as f: data = f.read()

        if data and has_private_key:
            self.private_key = PrivateKey(data)

            cert_len = struct.unpack("!H", self.private_key.data[385:387])[0]
            data = self.private_key.data[:387+cert_len]

        if not data:
            raise Exception("Can't create a destination with no data")

        self.data = data if type(data) == bytes else i2p_b64decode(data)
        self.base64 = data if type(data) == str else i2p_b64encode(data)

    def __repr__(self):
        return "<Destination: {}>".format(self.base32)

    @property
    def base32(self):
        """Base32 destination hash of this destination"""
        desthash = sha256(self.data).digest()
        return b32encode(desthash).decode()[:52].lower()
    
class PrivateKey(object):
    """I2P private key

    https://geti2p.net/spec/common-structures#keysandcert

    :param data: Base64 encoded data or binary data 
    """

    def __init__(self, data):
        #: Binary private key
        self.data = data if type(data) == bytes else i2p_b64decode(data)
        #: Base64 encoded private key
        self.base64 = data if type(data) == str else i2p_b64encode(data)

