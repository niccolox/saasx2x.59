"""Local TLS servers for the probe tests. They listen on 127.0.0.1 only and need no network."""

import asyncio
import ssl
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import ExitStack, asynccontextmanager

import trustme

type Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


def trusted_server_context(ca: trustme.CA) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ca.issue_cert("localhost").configure_cert(context)
    return context


def self_signed_server_context() -> ssl.SSLContext:
    unknown = trustme.CA()
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    with ExitStack() as files:
        cert = files.enter_context(unknown.cert_pem.tempfile())
        key = files.enter_context(unknown.private_key_pem.tempfile())
        context.load_cert_chain(cert, key)
    return context


@asynccontextmanager
async def serve(handler: Handler, context: ssl.SSLContext) -> AsyncGenerator[int]:
    """Serve TLS on a free port of 127.0.0.1 and yield the port."""
    server = await asyncio.start_server(handler, "127.0.0.1", 0, ssl=context)
    try:
        yield server.sockets[0].getsockname()[1]
    finally:
        server.close()
        server.abort_clients()
        await server.wait_closed()


def answer(raw_response: bytes, requests: list[bytes]) -> Handler:
    """Read one request head, keep it in `requests`, send `raw_response`, and close."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        requests.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(raw_response)
        await writer.drain()
        writer.close()

    return handle


async def never_answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.read()
    writer.close()
