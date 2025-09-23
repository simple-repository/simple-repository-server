# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from random import randbytes
import typing
import zlib

import httpx
import pytest
from pytest_httpserver import HTTPServer
from pytest_httpx import HTTPXMock

from simple_repository_server._http_response_iterator import HttpResponseIterator


@pytest.mark.asyncio
async def test_http_response_iterator__request_headers_passed_through(
        httpx_mock: HTTPXMock,
) -> None:
    # Check that we can pass headers through to the proxied request.
    httpx_mock.add_response()

    http_client = httpx.AsyncClient()
    _ = await HttpResponseIterator.create_iterator(
        http_client,
        'https://example.com/some/path',
        request_headers={'foo': 'bar', 'accept-encoding': 'wibble-wobble'},
    )

    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers['accept-encoding'] == 'wibble-wobble'
    assert 'foo' not in request.headers


_DEFLATE = zlib.compressobj(4, zlib.DEFLATED, -zlib.MAX_WBITS)


@pytest.mark.parametrize(
    ['input_content'],
    [
        ["This is the response content".encode('utf-8')],
        [randbytes(1024 * 1024 * 3)],  # 3 pages of chunked content
    ],
    ids=['utf8_encoded_bytes', 'multi_page_bytestring'],
)
@pytest.mark.parametrize(
    ['encoding_name', 'encoder', 'decoder'],
    [
        ['gzip', zlib.compress, zlib.decompress],
        # See https://stackoverflow.com/a/22311297/741316
        [
            'deflate',
            lambda data: _DEFLATE.compress(data) + _DEFLATE.flush(),
            lambda data: zlib.decompress(data, -zlib.MAX_WBITS),
        ],
        ['never-seen-before', lambda data: data + b'abc', lambda data: data[:-3]],
    ],
    ids=['gzip', 'deflate', 'never-seen-before'],
)
@pytest.mark.asyncio
async def test_http_response_iterator__response_remains_gzipped(
        httpserver: HTTPServer,
        input_content: bytes,
        encoding_name: str,
        encoder: typing.Callable[[bytes], bytes],
        decoder: typing.Callable[[bytes], bytes],
) -> typing.Any:
    # Serve some content as compressed bytes, and ensure that we can stream it
    # through the iterator (with the correct headers etc.).
    # We use a real test http server, to ensure that we are genuinely handling
    # gzipped responses correctly.
    try:
        compressed = encoder(input_content)
    except zlib.error:
        return pytest.xfail(reason='Known zlib error')
    httpserver.expect_request('/path').respond_with_data(
        compressed,
        headers={
            'content-type': 'application/octet-stream',
            'content-encoding': encoding_name,
        },
    )

    http_client = httpx.AsyncClient()
    response_it = await HttpResponseIterator.create_iterator(
        http_client,
        httpserver.url_for('/path'),
        request_headers={'foo': 'bar', 'accept-encoding': 'gzip'},
    )

    assert response_it.headers['content-type'] == 'application/octet-stream'
    assert response_it.headers['content-encoding'] == encoding_name
    assert int(response_it.headers['content-length']) == len(compressed)
    content = b''.join([chunk async for chunk in response_it])
    assert len(content) == len(compressed)
    assert decoder(content) == input_content


@pytest.mark.asyncio
async def test_http_response_iterator__follows_redirects(
        httpserver: HTTPServer,
) -> None:
    # Test that the HttpResponseIterator follows redirects properly
    final_content = b"This is the final content after redirect"

    # Set up redirect chain: /redirect -> /final
    httpserver.expect_request('/final').respond_with_data(
        final_content,
        headers={'content-type': 'application/octet-stream'},
    )
    httpserver.expect_request('/redirect').respond_with_data(
        b"",
        status=302,
        headers={'location': httpserver.url_for('/final')},
    )

    http_client = httpx.AsyncClient(follow_redirects=True)
    response_it = await HttpResponseIterator.create_iterator(
        http_client,
        httpserver.url_for('/redirect'),
    )

    # Should get the final content, not the redirect response
    assert response_it.status_code == 200
    content = b''.join([chunk async for chunk in response_it])
    assert content == final_content
