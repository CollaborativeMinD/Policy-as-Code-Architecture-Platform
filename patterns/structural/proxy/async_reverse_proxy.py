#!/usr/bin/env python3
"""Bounded asyncio/httpx HTTP/1.1 reverse proxy with round-robin balancing.

Install: python -m pip install 'httpx>=0.27,<1'
Run: python async_reverse_proxy.py --backend http://127.0.0.1:9001 \
     --backend http://127.0.0.1:9002 --port 8080

Scope: HTTP/1.1 requests, chunked or fixed request bodies, streamed responses.
No TLS termination, HTTP/2 downstream, WebSockets, CONNECT, or trailers.
Each downstream connection handles one request and closes deterministically.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import logging
import signal
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

LOG = logging.getLogger("async_reverse_proxy")
HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "proxy-connection",
})
BODYLESS = {204, 304}


class RequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Settings:
    backends: tuple[str, ...]
    host: str
    port: int
    max_body: int
    max_connections: int
    header_timeout: float
    body_timeout: float
    upstream_timeout: float


def strip_hop(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    extra = set()
    for name, value in headers:
        if name.lower() == "connection":
            extra.update(token.strip().lower() for token in value.split(","))
    return [(k, v) for k, v in headers if k.lower() not in HOP | extra]


async def read_headers(reader: asyncio.StreamReader, timeout: float) -> tuple[str, str, list[tuple[str, str]]]:
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout)
    except (asyncio.LimitOverrunError, asyncio.IncompleteReadError):
        raise RequestError(431, "request headers too large or incomplete") from None
    except TimeoutError:
        raise RequestError(408, "request header timeout") from None
    if len(raw) > 16384:
        raise RequestError(431, "request headers too large")
    try:
        lines = raw[:-4].decode("iso-8859-1").split("\r\n")
        method, target, version = lines[0].split(" ")
        if version != "HTTP/1.1" or not method.isascii() or not method.isalpha():
            raise ValueError("unsupported start line")
        if not target.startswith("/") or target.startswith("//") or "#" in target:
            raise ValueError("invalid origin-form target")
        headers = []
        for line in lines[1:]:
            if not line or line[0] in " \t" or ":" not in line:
                raise ValueError("invalid header")
            key, value = line.split(":", 1)
            if not key.isascii() or not key or any(not (c.isalnum() or c in "!#$%&'*+-.^_`|~") for c in key):
                raise ValueError("invalid header name")
            if any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in value):
                raise ValueError("invalid header value")
            headers.append((key, value.strip()))
    except ValueError:
        raise RequestError(400, "malformed HTTP/1.1 request") from None
    if sum(k.lower() == "host" for k, _ in headers) != 1:
        raise RequestError(400, "exactly one Host header required")
    return method, target, headers


async def read_body(reader: asyncio.StreamReader, headers: list[tuple[str, str]], limit: int, timeout: float) -> bytes:
    lengths = [v for k, v in headers if k.lower() == "content-length"]
    encodings = [v for k, v in headers if k.lower() == "transfer-encoding"]
    if lengths and encodings or len(lengths) > 1 or len(encodings) > 1:
        raise RequestError(400, "ambiguous request framing")
    if encodings:
        if encodings[0].lower().strip() != "chunked":
            raise RequestError(501, "unsupported transfer encoding")
        try:
            return await asyncio.wait_for(read_chunks(reader, limit), timeout)
        except TimeoutError:
            raise RequestError(408, "request body timeout") from None
    if not lengths:
        return b""
    if not lengths[0].isascii() or not lengths[0].isdecimal():
        raise RequestError(400, "invalid Content-Length")
    size = int(lengths[0])
    if size > limit:
        raise RequestError(413, "request body too large")
    try:
        return await asyncio.wait_for(reader.readexactly(size), timeout)
    except asyncio.IncompleteReadError:
        raise RequestError(400, "incomplete request body") from None
    except TimeoutError:
        raise RequestError(408, "request body timeout") from None


async def read_chunks(reader: asyncio.StreamReader, limit: int) -> bytes:
    result = bytearray()
    try:
        while True:
            line = await reader.readline()
            if not line.endswith(b"\r\n") or len(line) > 128:
                raise RequestError(400, "malformed chunk length")
            token = line[:-2].split(b";", 1)[0]
            if not token or any(c not in b"0123456789abcdefABCDEF" for c in token):
                raise RequestError(400, "invalid chunk length")
            size = int(token, 16)
            if size > limit - len(result):
                raise RequestError(413, "request body too large")
            if size == 0:
                if await reader.readexactly(2) != b"\r\n":
                    raise RequestError(400, "request trailers not supported")
                return bytes(result)
            result.extend(await reader.readexactly(size))
            if await reader.readexactly(2) != b"\r\n":
                raise RequestError(400, "invalid chunk terminator")
    except asyncio.IncompleteReadError:
        raise RequestError(400, "incomplete chunked body") from None


async def error(writer: asyncio.StreamWriter, status: int, message: str) -> None:
    reason = {400: "Bad Request", 408: "Request Timeout", 413: "Content Too Large",
              417: "Expectation Failed", 431: "Request Header Fields Too Large",
              500: "Internal Server Error", 501: "Not Implemented",
              502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout"}.get(status, "Error")
    body = (message + "\n").encode("utf-8")
    writer.write(f"HTTP/1.1 {status} {reason}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
    await writer.drain()


class Proxy:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rr = itertools.cycle(settings.backends)
        self.capacity = asyncio.Semaphore(settings.max_connections)
        self.client = httpx.AsyncClient(follow_redirects=False, trust_env=False,
                                        timeout=httpx.Timeout(settings.upstream_timeout),
                                        limits=httpx.Limits(max_connections=settings.max_connections))

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        acquired = False
        try:
            try:
                await asyncio.wait_for(self.capacity.acquire(), timeout=0.1)
                acquired = True
            except TimeoutError:
                await error(writer, 503, "proxy at capacity")
                return
            method, target, headers = await read_headers(reader, self.settings.header_timeout)
            if any(k.lower() == "expect" for k, _ in headers):
                raise RequestError(417, "Expect header not supported")
            body = await read_body(reader, headers, self.settings.max_body, self.settings.body_timeout)
            backend = next(self.rr)
            clean = [(k, v) for k, v in strip_hop(headers)
                     if k.lower() not in {"host", "content-length"}]
            clean.append(("Via", "1.1 asyncio-reverse-proxy"))
            url = backend + target
            async with self.client.stream(method, url, headers=clean, content=body) as response:
                await self.relay(writer, method, response)
        except RequestError as exc:
            await error(writer, exc.status, str(exc))
        except (httpx.TimeoutException, TimeoutError):
            await self.safe_error(writer, 504, "upstream timeout")
        except httpx.HTTPError as exc:
            LOG.warning("upstream failure: %s", type(exc).__name__)
            await self.safe_error(writer, 502, "upstream connection failure")
        except (ConnectionError, BrokenPipeError, asyncio.IncompleteReadError):
            pass
        except Exception:
            LOG.exception("unexpected proxy failure")
            await self.safe_error(writer, 500, "internal proxy error")
        finally:
            if acquired:
                self.capacity.release()
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    @staticmethod
    async def safe_error(writer: asyncio.StreamWriter, status: int, message: str) -> None:
        # Never append a second HTTP response after partial forwarding.
        if not getattr(writer, "_proxy_started", False):
            await error(writer, status, message)

    @staticmethod
    async def relay(writer: asyncio.StreamWriter, method: str, response: httpx.Response) -> None:
        status = response.status_code
        reason = response.reason_phrase.replace("\r", "").replace("\n", "")
        no_body = method.upper() == "HEAD" or status in BODYLESS or 100 <= status < 200
        headers = [(k, v) for k, v in strip_hop(list(response.headers.multi_items()))
                   if k.lower() not in {"content-length", "transfer-encoding"}]
        headers.append(("Connection", "close"))
        if not no_body:
            headers.append(("Transfer-Encoding", "chunked"))
        head = f"HTTP/1.1 {status} {reason}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers) + "\r\n"
        writer.write(head.encode("iso-8859-1"))
        # Marks that the status line is committed, not merely buffered.
        writer._proxy_started = True
        await writer.drain()
        if not no_body:
            async for chunk in response.aiter_raw(chunk_size=65536):
                if chunk:
                    writer.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                    await writer.drain()
            writer.write(b"0\r\n\r\n")
            await writer.drain()


async def serve(settings: Settings) -> None:
    proxy = Proxy(settings)
    async with proxy.client:
        server = await asyncio.start_server(proxy.handle, settings.host, settings.port, limit=16384)
        LOG.info("listening on %s:%d, backends=%s", settings.host, settings.port, settings.backends)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass
        async with server:
            await stop.wait()


def parse_args() -> Settings:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", action="append", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--max-body", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-connections", type=int, default=100)
    parser.add_argument("--header-timeout", type=float, default=5)
    parser.add_argument("--body-timeout", type=float, default=15)
    parser.add_argument("--upstream-timeout", type=float, default=30)
    args = parser.parse_args()
    for backend in args.backend:
        parsed = urlsplit(backend)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
            parser.error("backends must be http(s)://host[:port] without path, query, or credentials")
    if not (0 < args.port < 65536 and args.max_body > 0 and args.max_connections > 0):
        parser.error("port, max-body, and max-connections must be positive and valid")
    if min(args.header_timeout, args.body_timeout, args.upstream_timeout) <= 0:
        parser.error("timeouts must be positive")
    return Settings(tuple(b.rstrip("/") for b in args.backend), args.host, args.port,
                    args.max_body, args.max_connections, args.header_timeout,
                    args.body_timeout, args.upstream_timeout)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(serve(parse_args()))
    except KeyboardInterrupt:
        pass
