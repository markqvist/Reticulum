import asyncio

from . import sam
from . import exceptions
from . import utils
from .log import logger

def parse_reply(data):
    if not data:
        raise ConnectionAbortedError("Empty response: SAM API went offline")

    try:
        msg = sam.Message(data.decode().strip())
        logger.debug("SAM reply: "+str(msg))
    except:
        raise ConnectionAbortedError("Invalid SAM response")

    return msg


async def get_sam_socket(sam_address=sam.DEFAULT_ADDRESS, loop=None):
    """A couroutine used to create a new SAM socket.

    :param sam_address: (optional) SAM API address
    :param loop: (optional) event loop instance
    :return: A (reader, writer) pair
    """
    reader, writer = await asyncio.open_connection(*sam_address)
    writer.write(sam.hello("3.1", "3.1"))
    reply = parse_reply(await reader.readline())
    if reply.ok:
        return (reader, writer)
    else:
        writer.close()
        raise exceptions.SAM_EXCEPTIONS[reply["RESULT"]]()

async def dest_lookup(domain, sam_address=sam.DEFAULT_ADDRESS, 
                      loop=None):
    """A coroutine used to lookup a full I2P destination by .i2p domain or 
    .b32.i2p address.

    :param domain: Address to be resolved, can be a .i2p domain or a .b32.i2p 
                   address.
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :return: An instance of :class:`Destination`
    """
    reader, writer = await get_sam_socket(sam_address, loop)
    writer.write(sam.naming_lookup(domain))
    reply = parse_reply(await reader.readline())
    writer.close()
    if reply.ok:
        return sam.Destination(reply["VALUE"])
    else:
        raise exceptions.SAM_EXCEPTIONS[reply["RESULT"]]()

async def new_destination(sam_address=sam.DEFAULT_ADDRESS, loop=None,
                      sig_type=sam.Destination.default_sig_type):
    """A coroutine used to generate a new destination with a private key of a 
    chosen signature type.

    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :param sig_type: (optional) Signature type
    :return: An instance of :class:`Destination`
    """
    reader, writer = await get_sam_socket(sam_address, loop)
    writer.write(sam.dest_generate(sig_type))
    reply = parse_reply(await reader.readline())
    writer.close()
    return sam.Destination(reply["PRIV"], has_private_key=True)

async def create_session(session_name, sam_address=sam.DEFAULT_ADDRESS, 
                         loop=None, style="STREAM",
                         signature_type=sam.Destination.default_sig_type,
                         destination=None, options={}):
    """A coroutine used to create a new SAM session.

    :param session_name: Session nick name
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :param style: (optional) Session style, can be STREAM, DATAGRAM, RAW
    :param signature_type: (optional) If the destination is TRANSIENT, this 
                        signature type is used
    :param destination: (optional) Destination to use in this session. Can be 
                        a base64 encoded string, :class:`Destination` 
                        instance or None. TRANSIENT destination is used when it
                        is None.
    :param options: (optional) A dict object with i2cp options
    :return: A (reader, writer) pair
    """
    logger.debug("Creating session {}".format(session_name))
    if destination:
        if type(destination) == sam.Destination:
            destination = destination
        else:
            destination = sam.Destination(
                    destination, has_private_key=True)

        dest_string = destination.private_key.base64
    else:
        dest_string = sam.TRANSIENT_DESTINATION

    options = " ".join(["{}={}".format(k, v) for k, v in options.items()])

    reader, writer = await get_sam_socket(sam_address, loop)
    writer.write(sam.session_create(
            style, session_name, dest_string, options))

    reply = parse_reply(await reader.readline())
    if reply.ok:
        if not destination:
            destination = sam.Destination(
                    reply["DESTINATION"], has_private_key=True) 
        logger.debug(destination.base32)
        logger.debug("Session created {}".format(session_name))
        return (reader, writer)
    else:
        writer.close()
        raise exceptions.SAM_EXCEPTIONS[reply["RESULT"]]()

async def stream_connect(session_name, destination, 
                         sam_address=sam.DEFAULT_ADDRESS, loop=None):
    """A coroutine used to connect to a remote I2P destination.

    :param session_name: Session nick name
    :param destination: I2P destination to connect to
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :return: A (reader, writer) pair
    """
    logger.debug("Connecting stream {}".format(session_name))
    if isinstance(destination, str) and not destination.endswith(".i2p"):
        destination = sam.Destination(destination)
    elif isinstance(destination, str):
        destination = await dest_lookup(destination, sam_address, loop)

    reader, writer = await get_sam_socket(sam_address, loop)
    writer.write(sam.stream_connect(session_name, destination.base64,
                                           silent="false"))
    reply = parse_reply(await reader.readline())
    if reply.ok:
        logger.debug("Stream connected {}".format(session_name))
        return (reader, writer)
    else:
        writer.close()
        raise exceptions.SAM_EXCEPTIONS[reply["RESULT"]]()

async def stream_accept(session_name, sam_address=sam.DEFAULT_ADDRESS,
                        loop=None):
    """A coroutine used to accept a connection from the I2P network.

    :param session_name: Session nick name
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :return: A (reader, writer) pair
    """
    reader, writer = await get_sam_socket(sam_address, loop)
    writer.write(sam.stream_accept(session_name, silent="false"))
    reply = parse_reply(await reader.readline())
    if reply.ok:
        return (reader, writer)
    else:
        writer.close()
        raise exceptions.SAM_EXCEPTIONS[reply["RESULT"]]()

### Context managers

class Session:
    """Async SAM session context manager.

    :param session_name: Session nick name
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :param style: (optional) Session style, can be STREAM, DATAGRAM, RAW
    :param signature_type: (optional) If the destination is TRANSIENT, this 
                        signature type is used
    :param destination: (optional) Destination to use in this session. Can be 
                        a base64 encoded string, :class:`Destination` 
                        instance or None. TRANSIENT destination is used when it
                        is None.
    :param options: (optional) A dict object with i2cp options
    :return: :class:`Session` object
    """
    def __init__(self, session_name, sam_address=sam.DEFAULT_ADDRESS, 
                         loop=None, style="STREAM",
                         signature_type=sam.Destination.default_sig_type,
                         destination=None, options={}):
        self.session_name = session_name
        self.sam_address = sam_address
        self.loop = loop
        self.style = style
        self.signature_type = signature_type
        self.destination = destination
        self.options = options

    async def __aenter__(self):
        self.reader, self.writer = await create_session(self.session_name, 
                sam_address=self.sam_address, loop=self.loop, style=self.style, 
                signature_type=self.signature_type, 
                destination=self.destination, options=self.options)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        ### TODO handle exceptions
        self.writer.close()

class StreamConnection:
    """Async stream connection context manager.

    :param session_name: Session nick name
    :param destination: I2P destination to connect to
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :return: :class:`StreamConnection` object
    """
    def __init__(self, session_name, destination, 
                 sam_address=sam.DEFAULT_ADDRESS, loop=None):
        self.session_name = session_name
        self.sam_address = sam_address
        self.loop = loop
        self.destination = destination

    async def __aenter__(self):
        self.reader, self.writer = await stream_connect(self.session_name, 
                self.destination, sam_address=self.sam_address, loop=self.loop)
        self.read = self.reader.read
        self.write = self.writer.write
        return self

    async def __aexit__(self, exc_type, exc, tb):
        ### TODO handle exceptions
        self.writer.close()

class StreamAcceptor:
    """Async stream acceptor context manager.

    :param session_name: Session nick name
    :param sam_address: (optional) SAM API address
    :param loop: (optional) Event loop instance
    :return: :class:`StreamAcceptor` object
    """
    def __init__(self, session_name, sam_address=sam.DEFAULT_ADDRESS, 
                 loop=None):
        self.session_name = session_name
        self.sam_address = sam_address
        self.loop = loop

    async def __aenter__(self):
        self.reader, self.writer = await stream_accept(self.session_name, 
                        sam_address=self.sam_address, loop=self.loop)
        self.read = self.reader.read
        self.write = self.writer.write
        return self

    async def __aexit__(self, exc_type, exc, tb):
        ### TODO handle exceptions
        self.writer.close()
