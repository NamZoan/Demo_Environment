from __future__ import annotations

import asyncio
import hmac
import ipaddress
import os
import struct
from collections.abc import Mapping


def parse_credentials(value: str) -> dict[str, str]:
    credentials: dict[str, str] = {}
    for entry in value.split(","):
        username, separator, password = entry.partition(":")
        if not separator or not username or not password or username in credentials:
            raise ValueError("PROXY_USERS must contain unique username:password entries")
        credentials[username] = password
    return credentials


class Socks5Server:
    def __init__(
        self,
        username: str | Mapping[str, str],
        password: str | None = None,
        host: str = "0.0.0.0",
        port: int = 18080,
    ):
        if isinstance(username, Mapping):
            if password is not None:
                raise ValueError("password is not used with multiple proxy accounts")
            credentials = dict(username)
        else:
            if password is None:
                raise ValueError("proxy password is required")
            credentials = {username: password}
        if not credentials:
            raise ValueError("proxy username and password are required")
        if any(len(user.encode()) > 255 or len(secret.encode()) > 255 for user, secret in credentials.items()):
            raise ValueError("proxy credentials must fit SOCKS5 authentication fields")
        self.credentials = {user.encode(): secret.encode() for user, secret in credentials.items()}
        self.host = host
        self.port = port

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle_client, self.host, self.port)

    async def handle_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        remote_writer: asyncio.StreamWriter | None = None
        try:
            if not await self._authenticate(client_reader, client_writer):
                return
            destination = await self._read_connect_request(client_reader, client_writer)
            if destination is None:
                return
            try:
                remote_reader, remote_writer = await asyncio.open_connection(*destination)
            except OSError:
                await self._reply(client_writer, 0x05)
                return
            await self._reply(client_writer, 0x00)
            await asyncio.gather(
                self._pipe(client_reader, remote_writer),
                self._pipe(remote_reader, client_writer),
            )
        except (asyncio.IncompleteReadError, ConnectionError, OSError, ValueError):
            return
        finally:
            client_writer.close()
            await client_writer.wait_closed()
            if remote_writer is not None:
                remote_writer.close()
                await remote_writer.wait_closed()

    async def _authenticate(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        version, method_count = struct.unpack("!BB", await reader.readexactly(2))
        methods = await reader.readexactly(method_count)
        if version != 5 or 0x02 not in methods:
            writer.write(b"\x05\xff")
            await writer.drain()
            return False
        writer.write(b"\x05\x02")
        await writer.drain()

        auth_version, username_length = struct.unpack("!BB", await reader.readexactly(2))
        username = await reader.readexactly(username_length)
        password_length = (await reader.readexactly(1))[0]
        password = await reader.readexactly(password_length)
        valid = (
            auth_version == 1
            and username in self.credentials
            and hmac.compare_digest(password, self.credentials.get(username, b""))
        )
        writer.write(b"\x01\x00" if valid else b"\x01\xff")
        await writer.drain()
        return valid

    async def _read_connect_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> tuple[str, int] | None:
        version, command, _reserved, address_type = struct.unpack("!BBBB", await reader.readexactly(4))
        if address_type == 1:
            host = str(ipaddress.ip_address(await reader.readexactly(4)))
        elif address_type == 3:
            host = (await reader.readexactly(1))[0]
            host = (await reader.readexactly(host)).decode("idna")
        elif address_type == 4:
            host = str(ipaddress.ip_address(await reader.readexactly(16)))
        else:
            await self._reply(writer, 0x08)
            return None
        port = struct.unpack("!H", await reader.readexactly(2))[0]
        if version != 5 or command != 1:
            await self._reply(writer, 0x07)
            return None
        return host, port

    @staticmethod
    async def _reply(writer: asyncio.StreamWriter, status: int) -> None:
        writer.write(b"\x05" + bytes([status]) + b"\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

    @staticmethod
    async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()


async def run() -> None:
    users = os.getenv("PROXY_USERS")
    credentials = parse_credentials(users) if users else {os.environ["PROXY_USERNAME"]: os.environ["PROXY_PASSWORD"]}
    host = os.getenv("PROXY_HOST", "0.0.0.0")
    port = int(os.getenv("PROXY_PORT", "18080"))
    proxy = Socks5Server(credentials, host=host, port=port)
    server = await proxy.start()
    print(f"SOCKS5 proxy listening on {host}:{port}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(run())
