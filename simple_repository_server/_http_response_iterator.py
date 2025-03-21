# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import annotations

import typing

import httpx


class HttpResponseIterator:
    """
    A class providing a generator to iterate over response body bytes from an httpx request.

    This class creates an iterator that allows you to iterate over the bytes of a response body
    obtained from an httpx request. Additionally, it provides access to the response status code
    and headers before the streaming response is constructed. It is particularly designed to be
    used with Starlette's streaming responses, enabling access to headers and status code before
    the response is returned by an API endpoint. The class will keep the httpx session alive
    until the entire response content is accessed.
    """

    PROXIED_REQUEST_HEADERS = {
        'accept',
        'user-agent',
        'accept-encoding',
        'if-unmodified-since',
        'if-range', 'if-none-match',
        'if-modified-since',
        'if-match',
        'range',
        'referer',
    }

    def __init__(self, http_client: httpx.AsyncClient, url: str):
        """
        Do not call the constructor of this class directly.
        Use StreamResponseIterator.create_iterator.
        """
        self.http_client = http_client
        self.url: str = url
        self.status_code: int
        self.headers: typing.Mapping[str, str]
        self._agen: typing.AsyncGenerator[bytes, None]

    def __aiter__(self) -> HttpResponseIterator:
        return self

    async def __anext__(self) -> bytes:
        return await self._agen.__anext__()

    @classmethod
    async def create_iterator(
        cls,
        http_client: httpx.AsyncClient,
        url: str,
        *,
        request_headers: typing.Mapping[str, str] | None = None,
    ) -> HttpResponseIterator:
        iterator = HttpResponseIterator(
            http_client=http_client,
            url=url,
        )
        request_headers = request_headers or {}
        headers = {
            header_name: header_value for header_name, header_value in request_headers.items()
            if header_name.lower() in cls.PROXIED_REQUEST_HEADERS
        }

        async def agenerator() -> typing.AsyncGenerator[bytes, None]:
            async with iterator.http_client.stream(
                    method="GET",
                    url=iterator.url,
                    headers=headers,
            ) as resp:
                # Expose the response status and headers.
                iterator.status_code, iterator.headers = resp.status_code, resp.headers

                # The first time that anext is called, set status_code and
                # headers, without yielding the first byte of the stream.
                yield b""
                async for chunk in resp.aiter_raw(1024 * 1024):
                    yield chunk

        iterator._agen = agenerator()
        # Call anext to set the values of status_code and headers.
        await iterator.__anext__()

        return iterator
