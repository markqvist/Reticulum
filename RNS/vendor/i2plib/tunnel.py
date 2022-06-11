import logging
import asyncio
import argparse

from . import sam 
from . import aiosam
from . import utils
from .log import logger

BUFFER_SIZE = 65536

async def proxy_data(reader, writer):
    """Proxy data from reader to writer"""
    try:
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            writer.write(data)
    except Exception as e:
        logger.debug('proxy_data_task exception {}'.format(e))
    finally:
        try:
            writer.close()
        except RuntimeError:
            pass
        logger.debug('close connection')

class I2PTunnel(object):
    """Base I2P Tunnel object, not to be used directly

    :param local_address: A local address to use for a tunnel. 
                          E.g. ("127.0.0.1", 6668)
    :param destination: (optional) Destination to use for this tunnel. Can be 
                        a base64 encoded string, :class:`Destination`
                        instance or None. A new destination is created when it
                        is None.
    :param session_name: (optional) Session nick name. A new session nickname is
                        generated if not specified.
    :param options: (optional) A dict object with i2cp options
    :param loop: (optional) Event loop instance
    :param sam_address: (optional) SAM API address
    """

    def __init__(self, local_address, destination=None, session_name=None, 
                 options={}, loop=None, sam_address=sam.DEFAULT_ADDRESS):
        self.local_address = local_address
        self.destination = destination
        self.session_name = session_name or utils.generate_session_id()
        self.options = options
        self.loop = loop
        self.sam_address = sam_address

    async def _pre_run(self):
        if not self.destination:
            self.destination = await aiosam.new_destination(
                sam_address=self.sam_address, loop=self.loop)
        _, self.session_writer = await aiosam.create_session(
                self.session_name, style=self.style, options=self.options,
                sam_address=self.sam_address, 
                loop=self.loop, destination=self.destination)

    def stop(self):
        """Stop the tunnel"""
        self.session_writer.close()

class ClientTunnel(I2PTunnel):
    """Client tunnel, a subclass of tunnel.I2PTunnel

    If you run a client tunnel with a local address ("127.0.0.1", 6668) and
    a remote destination "irc.echelon.i2p", all connections to 127.0.0.1:6668 
    will be proxied to irc.echelon.i2p.

    :param remote_destination: Remote I2P destination, can be either .i2p 
                        domain, .b32.i2p address, base64 destination or 
                        :class:`Destination` instance
    """

    def __init__(self, remote_destination, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style = "STREAM"
        self.remote_destination = remote_destination

    async def run(self):
        """A coroutine used to run the tunnel"""
        await self._pre_run()

        self.status = { "setup_ran": False, "setup_failed": False, "exception": None, "connect_tasks": [] }
        async def handle_client(client_reader, client_writer):
            """Handle local client connection"""
            try:
                sc_task = aiosam.stream_connect(
                        self.session_name, self.remote_destination, 
                        sam_address=self.sam_address, loop=self.loop)
                self.status["connect_tasks"].append(sc_task)
                
                remote_reader, remote_writer = await sc_task
                asyncio.ensure_future(proxy_data(remote_reader, client_writer), 
                                      loop=self.loop)
                asyncio.ensure_future(proxy_data(client_reader, remote_writer),
                                      loop=self.loop)

            except Exception as e:
                self.status["setup_ran"] = True
                self.status["setup_failed"] = True
                self.status["exception"] = e


        try:
            self.server = await asyncio.start_server(handle_client, *self.local_address)
            self.status["setup_ran"] = True

        except Exception as e:
            self.status["setup_ran"] = True
            self.status["setup_failed"] = True
            self.status["exception"] = e

    def stop(self):
        super().stop()
        self.server.close()

class ServerTunnel(I2PTunnel):
    """Server tunnel, a subclass of tunnel.I2PTunnel

    If you want to expose a local service 127.0.0.1:80 to the I2P network, run
    a server tunnel with a local address ("127.0.0.1", 80). If you don't 
    provide a private key or a session name, it will use a TRANSIENT 
    destination.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style = "STREAM"

    async def run(self):
        """A coroutine used to run the tunnel"""
        await self._pre_run()

        self.status = { "setup_ran": False, "setup_failed": False, "exception": None, "connect_tasks": [] }
        async def handle_client(incoming, client_reader, client_writer):
            try:
                # data and dest may come in one chunk
                dest, data = incoming.split(b"\n", 1) 
                remote_destination = sam.Destination(dest.decode())
                logger.debug("{} client connected: {}.b32.i2p".format(
                    self.session_name, remote_destination.base32))
            
            except Exception as e:
                self.status["exception"] = e
                self.status["setup_failed"] = True
                data = None

            try:
                sc_task = asyncio.wait_for(
                        asyncio.open_connection(
                           host=self.local_address[0], 
                           port=self.local_address[1]),
                        timeout=5)
                self.status["connect_tasks"].append(sc_task)

                remote_reader, remote_writer = await sc_task
                if data: remote_writer.write(data)
                asyncio.ensure_future(proxy_data(remote_reader, client_writer),
                                      loop=self.loop)
                asyncio.ensure_future(proxy_data(client_reader, remote_writer),
                                      loop=self.loop)

            except ConnectionRefusedError:
                client_writer.close()
                self.status["exception"] = e
                self.status["setup_failed"] = True

        async def server_loop():
            try:
                while True:
                    client_reader, client_writer = await aiosam.stream_accept(
                            self.session_name, sam_address=self.sam_address, 
                            loop=self.loop)
                    incoming = await client_reader.read(BUFFER_SIZE)
                    asyncio.ensure_future(handle_client(
                        incoming, client_reader, client_writer), loop=self.loop)
            except asyncio.CancelledError:
                pass

        self.server_loop = asyncio.ensure_future(server_loop(), loop=self.loop)
        self.status["setup_ran"] = True

    def stop(self):
        super().stop()
        self.server_loop.cancel()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('type', metavar="TYPE", choices=('server', 'client'),
                        help="Tunnel type (server or client)")
    parser.add_argument('address', metavar="ADDRESS", 
                        help="Local address (e.g. 127.0.0.1:8000)")
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Debugging')
    parser.add_argument('--key', '-k', default='', metavar='PRIVATE_KEY',
                        help='Path to private key file')
    parser.add_argument('--destination', '-D', default='', 
                        metavar='DESTINATION', help='Remote destination')
    args = parser.parse_args()

    SAM_ADDRESS = utils.get_sam_address()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    loop = asyncio.get_event_loop()
    loop.set_debug(args.debug)

    if args.key:
        destination = sam.Destination(path=args.key, has_private_key=True)
    else:
        destination = None

    local_address = utils.address_from_string(args.address)

    if args.type == "client":
        tunnel = ClientTunnel(args.destination, local_address, loop=loop, 
                destination=destination, sam_address=SAM_ADDRESS)
    elif args.type == "server":
        tunnel = ServerTunnel(local_address, loop=loop, destination=destination, 
                sam_address=SAM_ADDRESS)

    asyncio.ensure_future(tunnel.run(), loop=loop)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        tunnel.stop()
    finally:
        loop.stop()
        loop.close()
