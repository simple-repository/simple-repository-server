# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import annotations

import typing

import aiohttp


class HttpResponseIterator:
    """
    A class providing a generator to iterate over response body bytes from an aiohttp request.

    This class creates an iterator that allows you to iterate over the bytes of a response body
    obtained from an aiohttp request. Additionally, it provides access to the response status code
    and headers before the streaming response is constructed. It is particularly designed to be
    used with Starlette's streaming responses, enabling access to headers and status code before
    the response is returned by an API endpoint. The class will keep the aiohttp session alive
    until the entire response content is accessed.
    """

    def __init__(self, session: aiohttp.ClientSession, url: str):
        """
        Do not call the constructor of this class directly.
        Use StreamResponseIterator.create_iterator.
        """
        self.session = session
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
        session: aiohttp.ClientSession,
        url: str,
    ) -> HttpResponseIterator:
        iterator = HttpResponseIterator(
            session=session,
            url=url,
        )

        async def agenerator() -> typing.AsyncGenerator[bytes, None]:
            async with iterator.session.get(url=iterator.url) as resp:
                iterator.status_code, iterator.headers = resp.status, resp.headers
                # The first time that anext is called, set stauts_code and
                # headers, without yielding the first byte of the stream.
                yield b""
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    yield chunk

        iterator._agen = agenerator()
        # Call anext to set the values of stauts_code and headers.
        await iterator.__anext__()

        return iterator
