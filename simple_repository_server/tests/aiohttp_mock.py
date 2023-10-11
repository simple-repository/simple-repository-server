# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import json
import types
import typing
from unittest import mock

import aiohttp


class MockClientResponse:
    def __init__(
        self,
        status: int = 200,
        content: str = '',
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._content_str = content
        self._content_bytes = content.encode('utf-8')
        self.headers = headers or {}

    async def json(self) -> typing.Any:
        return json.loads(self._content_str)

    async def text(self) -> str:
        return self._content_str

    def raise_for_status(self) -> None:
        if 400 <= self.status < 600:
            raise aiohttp.ClientResponseError(None, None, status=self.status)

    @property
    def content(self) -> mock.Mock:
        mock_content = mock.Mock()
        mock_content.iter_chunked = self._iter_chunked
        return mock_content

    async def _iter_chunked(self, chunk_size: int) -> typing.AsyncGenerator[bytes, None]:
        for i in range(0, len(self._content_bytes), chunk_size):
            yield self._content_bytes[i:i + chunk_size]


class MockRequestContextManager:
    def __init__(self, response_mock: MockClientResponse) -> None:
        self.response_mock = response_mock

    async def __aenter__(self) -> MockClientResponse:
        return self.response_mock

    async def __aexit__(
        self,
        exc_type: type,
        exc_val: Exception,
        exc_tb: types.TracebackType,
    ) -> None:
        pass


class MockClientSession:
    def __init__(
        self,
        status: int = 200,
        content: str = "",
        headers: dict[str, str] | None = None,
        raise_status_code: int | None = None,
    ) -> None:
        response_mock = MockClientResponse(
            status=status,
            content=content,
            headers=headers,
        )

        self._response_context = MockRequestContextManager(
            response_mock=response_mock,
        )

        self._error = aiohttp.ClientResponseError(
            request_info=mock.Mock(spec=aiohttp.RequestInfo),
            history=(),
            status=raise_status_code,
        ) if raise_status_code else None

    def get(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> MockRequestContextManager:
        if self._error:
            raise self._error
        return self._response_context

    def head(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> MockRequestContextManager:
        if self._error:
            raise self._error
        return self._response_context

    def post(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> MockRequestContextManager:
        if self._error:
            raise self._error
        return self._response_context

    def delete(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> MockRequestContextManager:
        if self._error:
            raise self._error
        return self._response_context
