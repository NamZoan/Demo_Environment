import asyncio

import pytest

from proxy.server import Socks5Server


def run(coro):
    return asyncio.run(coro)


async def start_echo_server():
    async def echo(reader, writer):
        writer.write(await reader.read(4096))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    return await asyncio.start_server(echo, "127.0.0.1", 0)


def test_socks5_rejects_invalid_credentials():
    async def scenario():
        proxy = Socks5Server("user", "correct", "127.0.0.1", 0)
        server = await proxy.start()
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        writer.write(b"\x05\x01\x02")
        assert await reader.readexactly(2) == b"\x05\x02"
        writer.write(b"\x01\x04user\x05wrong")
        assert await reader.readexactly(2) == b"\x01\xff"

        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()

    run(scenario())


def test_socks5_connect_relays_data_after_authentication():
    async def scenario():
        upstream = await start_echo_server()
        upstream_port = upstream.sockets[0].getsockname()[1]
        proxy = Socks5Server("user", "correct", "127.0.0.1", 0)
        server = await proxy.start()
        proxy_port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)

        writer.write(b"\x05\x01\x02")
        assert await reader.readexactly(2) == b"\x05\x02"
        writer.write(b"\x01\x04user\x07correct")
        assert await reader.readexactly(2) == b"\x01\x00"
        writer.write(b"\x05\x01\x00\x01\x7f\x00\x00\x01" + upstream_port.to_bytes(2, "big"))
        reply = await reader.readexactly(10)
        assert reply[:2] == b"\x05\x00"

        writer.write(b"hello through proxy")
        await writer.drain()
        assert await reader.readexactly(19) == b"hello through proxy"

        writer.close()
        await writer.wait_closed()
        server.close()
        upstream.close()
        await server.wait_closed()
        await upstream.wait_closed()

    run(scenario())
