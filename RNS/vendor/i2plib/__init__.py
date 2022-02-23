"""
A modern asynchronous library for building I2P applications. 
"""

from .__version__ import (
    __title__, __description__, __url__, __version__,
    __author__, __author_email__, __license__, __copyright__
)

from .sam import Destination, PrivateKey

from .aiosam import (
    get_sam_socket, dest_lookup, new_destination, 
    create_session, stream_connect, stream_accept,
    Session, StreamConnection, StreamAcceptor
)

from .tunnel import ClientTunnel, ServerTunnel

from .utils import get_sam_address

from .exceptions import (
     CantReachPeer, DuplicatedDest, DuplicatedId, I2PError,
     InvalidId, InvalidKey, KeyNotFound, PeerNotFound, Timeout,
)
