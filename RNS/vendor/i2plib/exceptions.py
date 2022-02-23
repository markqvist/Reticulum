# SAM exceptions

class SAMException(IOError):
    """Base class for SAM exceptions"""

class CantReachPeer(SAMException):
    """The peer exists, but cannot be reached"""

class DuplicatedDest(SAMException):
    """The specified Destination is already in use"""

class DuplicatedId(SAMException):
    """The nickname is already associated with a session"""

class I2PError(SAMException):
    """A generic I2P error"""

class InvalidId(SAMException):
    """STREAM SESSION ID doesn't exist"""

class InvalidKey(SAMException):
    """The specified key is not valid (bad format, etc.)"""

class KeyNotFound(SAMException):
    """The naming system can't resolve the given name"""

class PeerNotFound(SAMException):
    """The peer cannot be found on the network"""

class Timeout(SAMException):
    """The peer cannot be found on the network"""

SAM_EXCEPTIONS = {
    "CANT_REACH_PEER": CantReachPeer,
    "DUPLICATED_DEST": DuplicatedDest,
    "DUPLICATED_ID": DuplicatedId,
    "I2P_ERROR": I2PError,
    "INVALID_ID": InvalidId,
    "INVALID_KEY": InvalidKey,
    "KEY_NOT_FOUND": KeyNotFound,
    "PEER_NOT_FOUND": PeerNotFound,
    "TIMEOUT": Timeout,
}

