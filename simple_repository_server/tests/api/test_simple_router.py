# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import pathlib
import typing
from unittest import mock

from fastapi import FastAPI
import httpx
import pytest
from pytest_httpx import HTTPXMock
from simple_repository import errors, model
from simple_repository.components.core import SimpleRepository
from starlette.testclient import TestClient

import simple_repository_server.routers.simple as simple_router


@pytest.fixture
def mock_repo() -> mock.AsyncMock:
    mock_repo = mock.AsyncMock(spec=SimpleRepository)
    return mock_repo


@pytest.fixture
def client(tmp_path: pathlib.PosixPath, mock_repo: mock.AsyncMock) -> typing.Generator[TestClient, None, None]:
    app = FastAPI()
    http_client = httpx.AsyncClient()
    app.include_router(simple_router.build_router(mock_repo, http_client=http_client))

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "headers", [{}, {"Accept": "text/html"}, {"Accept": "*/*"}],
)
def test_simple_project_list(client: TestClient, headers: dict[str, str], mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_list.return_value = model.ProjectList(
        meta=model.Meta("1.0"),
        projects=frozenset([
            model.ProjectListElement("a"),
        ]),
    )

    expected = """<!DOCTYPE html>
    <html>
    <head>
        <meta name="pypi:repository-version" content="1.0">
        <title>Simple index</title>
    </head>
    <body>
<a href="a/">a</a><br/>
</body>
</html>"""

    response = client.get("/simple/", headers=headers)
    assert response.status_code == 200
    assert response.text == expected


@pytest.mark.parametrize(
    "headers", [{}, {"Accept": "text/html"}, {"Accept": "*/*"}],
)
def test_simple_project_page(client: TestClient, headers: dict[str, str], mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_page.return_value = model.ProjectDetail(
        meta=model.Meta("1.0"),
        name="name",
        files=(model.File("name.whl", "original_url", {}),),
    )

    expected = """<!DOCTYPE html>
    <html>
    <head>
        <meta name="pypi:repository-version" content="1.0">
        <title>Links for name</title>
    </head>
    <body>
    <h1>Links for name</h1>
<a href="../../resources/name/name.whl">name.whl</a><br/>
</body>
</html>"""

    response = client.get("/simple/name/", headers=headers)
    assert response.status_code == 200
    assert response.text == expected


def test_simple_package_releases__not_normalized(client: TestClient, mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    response = client.get("/simple/not_Normalized/", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers['location'] == '../not-normalized/'


def test_simple_package_releases__no_trailing_slash(client: TestClient, mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    response = client.get("/simple/some-project", follow_redirects=False)
    assert response.status_code == 307  # Provided by FastAPI itself


@pytest.mark.asyncio
async def test_simple_package_releases__package_not_found(client: TestClient, mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_page.side_effect = errors.PackageNotFoundError(
        package_name="ghost",
    )

    response = client.get("/simple/ghost")
    assert response.status_code == 404
    assert response.json() == {
        'detail': "Package 'ghost' was not found in "
        "the configured source",
    }


def test_get_resource__http_redirect(mock_repo: mock.AsyncMock) -> None:
    mock_repo.get_resource.return_value = model.HttpResource(
        url="http://my_url",
    )

    http_client = httpx.AsyncClient()
    app = FastAPI()
    app.include_router(simple_router.build_router(mock_repo, http_client=http_client))
    client = TestClient(app)

    response = client.get("/resources/numpy/numpy-1.0-ciao.whl", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://my_url"


def test_get_resource__http_streaming(mock_repo: mock.AsyncMock, httpx_mock: HTTPXMock) -> None:
    mock_repo.get_resource.return_value = model.HttpResource(
        url="http://my_url",
    )

    httpx_mock.add_response(
        status_code=201,
        headers={"my_header": "header"},
        text="b1b2b3",
    )
    http_client = httpx.AsyncClient()
    app = FastAPI()
    app.include_router(simple_router.build_router(mock_repo, http_client=http_client, stream_http_resources=True))
    client = TestClient(app)

    response = client.get("/resources/numpy/numpy-1.0-ciao.whl", follow_redirects=False)
    assert response.status_code == 201
    assert response.headers.get("my_header") == "header"
    assert response.text == "b1b2b3"


def test_get_resource_not_found(client: TestClient, mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_resource.side_effect = errors.ResourceUnavailable("resource_name")
    response = client.get("/resources/numpy/numpy1.0.whl")
    assert response.status_code == 404


def test_unsupported_serialization(client: TestClient) -> None:
    response = client.get("/simple/", headers={"accept": "pizza/margherita"})
    assert response.status_code == 406

    response = client.get("/simple/numpy/", headers={"accept": "application/vnd.pypi.simple.v2+html"})
    assert response.status_code == 406


def test_simple_project_page_json(client: TestClient, mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_page.return_value = model.ProjectDetail(
        meta=model.Meta("1.0"),
        name="name",
        files=(model.File("name.whl", "url", {}),),
    )

    expected = (
        '{"meta": {"api-version": "1.0"}, "name": "name",'
        ' "files": [{"filename": "name.whl", "url": '
        '"../../resources/name/name.whl", "hashes": {}}]}'
    )

    response = client.get("/simple/name/", headers={"accept": "application/vnd.pypi.simple.v1+json"})
    assert response.status_code == 200
    assert response.text == expected
    assert response.headers["Content-Type"] == "application/vnd.pypi.simple.v1+json"


def test_simple_project_list_json(client: TestClient, mock_repo: mock.AsyncMock) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_list.return_value = model.ProjectList(
        meta=model.Meta("1.0"),
        projects=frozenset([
            model.ProjectListElement("a"),
        ]),
    )

    expected = '{"meta": {"api-version": "1.0"}, "projects": [{"name": "a"}]}'

    response = client.get("/simple/", headers={"accept": "application/vnd.pypi.simple.v1+json"})
    assert response.status_code == 200
    assert response.text == expected


@pytest.mark.parametrize(
    "url_format", [
        "application/vnd.pypi.simple.v1+json",
        "application/vnd.pypi.simple.v1+html",
    ],
)
def test_simple_project_page__json_url_params(
    client: TestClient,
    url_format: str,
    mock_repo: mock.AsyncMock,
) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_page.return_value = model.ProjectDetail(
        meta=model.Meta("1.0"),
        name="name",
        files=(model.File("name.whl", "url", {}),),
    )

    response = client.get(f"/simple/name/?format={url_format}")
    assert response.headers.get("content-type") == url_format


@pytest.mark.parametrize(
    "url_format", [
        "application/vnd.pypi.simple.v1+json",
        "application/vnd.pypi.simple.v1+html",
    ],
)
def test_simple_project_list__json_url_params(
    client: TestClient,
    url_format: str,
    mock_repo: mock.AsyncMock,
) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_project_list.return_value = model.ProjectList(
        meta=model.Meta("1.0"),
        projects=frozenset([
            model.ProjectListElement("a"),
        ]),
    )

    response = client.get(f"/simple/?format={url_format}")
    assert response.headers.get("content-type") == url_format


@pytest.mark.parametrize(
    ['headers', 'expected_return_code'],
    [
        [{}, 200],
        [{"If-None-Match": '"45447b7afbd5"'}, 304],
        [{"If-None-Match": '"not-the-etag"'}, 200],
    ],
)
def test_get_resource__metadata(
        client: TestClient,
        mock_repo: mock.AsyncMock,
        headers: dict[str, str],
        expected_return_code: int,
) -> None:
    assert isinstance(client.app, FastAPI)
    mock_repo.get_resource.return_value = model.TextResource(
        text="metadata",
    )
    expected_etag = '"45447b7afbd5"'

    response = client.get("/resources/numpy/numpy-1.0-ciao.whl.metadata", headers=headers)
    assert response.status_code == expected_return_code
    # The etag must always be returned, see the following for details:
    # https://github.com/simple-repository/simple-repository-server/issues/6#issue-2317360891
    assert response.headers.get("etag") == expected_etag


@pytest.mark.parametrize(
    ['headers', 'expected_return_code'],
    [
        [{}, 200],
        [{"If-None-Match": '"430fddbf0a7ab4aebc1389262dbe2404"'}, 304],
        [{"If-None-Match": '"not-the-etag"'}, 200],
    ],
)
def test_get_resource__local(
    client: TestClient,
    mock_repo: mock.AsyncMock,
    tmp_path: pathlib.Path,
    headers: dict[str, str],
    expected_return_code: int,
) -> None:
    local_resource = tmp_path / "my_file"
    local_resource.write_text("hello!")
    expected_tag = '"430fddbf0a7ab4aebc1389262dbe2404"'

    assert isinstance(client.app, FastAPI)
    mock_repo.get_resource.return_value = model.LocalResource(
        path=local_resource,
        context=model.Context(etag=expected_tag),
    )

    response = client.get("/resources/numpy/numpy-1.0-ciao.whl", headers=headers)
    assert response.status_code == expected_return_code
    # The etag must always be returned, see the following for details:
    # https://github.com/simple-repository/simple-repository-server/issues/6#issue-2317360891
    assert response.headers.get("etag") == expected_tag
