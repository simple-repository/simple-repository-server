# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from unittest import mock

from packaging.version import Version
import pytest
from simple_repository import model
from starlette.datastructures import URL

from simple_repository_server import utils


def test_replace_urls() -> None:
    page = model.ProjectDetail(
        meta=model.Meta("1.0"),
        name="numpy",
        files=(model.File("numpy-1.0-any.whl", "old_url", {}),),
    )

    with mock.patch("simple_repository_server.utils.relative_url_for", return_value="new_url"):
        page = utils.replace_urls(page, "numpy", mock.Mock())

    assert page.files == (
        model.File("numpy-1.0-any.whl", "new_url", {}),
    )


@pytest.mark.parametrize(
    "origin, destination, result", [
        (
            "https://simple-repository/simple/numpy/",
            "https://simple-repository/resources/numpy/numpy-1.0.whl",
            "../../resources/numpy/numpy-1.0.whl",
        ), (
            "https://simple-repository/simple/Numpy/",
            "https://simple-repository/simple/numpy/",
            "../numpy/",
        ), (
            "https://simple-repository/simple/Numpy",
            "https://simple-repository/simple/numpy",
            "numpy",
        ), (
            "https://simple-repository/simple/",
            "https://simple-repository/simple/numpy/",
            "numpy/",
        ), (
            "https://simple-repository/simple/",
            "https://simple-repository/simple/",
            "",
        ), (
            "https://simple-repository/simple",
            "https://simple-repository/simple",
            "simple",
        ), (
            "https://simple-repository/simple",
            "https://simple-repository/simple/",
            "simple/",
        ), (
            "https://simple-repository/simple/",
            "https://simple-repository/simple",
            "../simple",
        ), (
            "https://simple-repository/simple/project/numpy",
            "https://simple-repository/simple/",
            "../",
        ),
    ],
)
def test_url_as_relative(destination: str, origin: str, result: str) -> None:
    assert utils.url_as_relative(
        destination_absolute_url=destination,
        origin_absolute_url=origin,
    ) == result


@pytest.mark.parametrize(
    "origin, destination", [
        (
            "http://simple-repository/simple/numpy/",
            "https://simple-repository/resources/numpy/numpy-1.0.whl",
        ), (
            "https://simple-repository/simple/Numpy/",
            "https://simple-repository2/simple/numpy/",
        ), (
            "https://simple-repository:81/simple/Numpy",
            "https://simple-repository:80/simple/numpy",
        ), (
            "https://simple-repository/simple/numpy/",
            "../tensorflow",
        ), (
            "../tensorflow",
            "https://simple-repository/simple/numpy/",
        ),
    ],
)
def test_url_as_relative__invalid(origin: str, destination: str) -> None:
    with pytest.raises(
        ValueError,
        match=f"Cannot create a relative url from {origin} to {destination}",
    ):
        utils.url_as_relative(
            destination_absolute_url=destination,
            origin_absolute_url=origin,
        )


def test_relative_url_for() -> None:
    request_mock = mock.Mock(
        url=URL("https://url/number/one"),
        url_for=mock.Mock(return_value=URL("https://url/number/one")),
    )
    url_as_relative_mock = mock.Mock()

    with mock.patch("simple_repository_server.utils.url_as_relative", url_as_relative_mock):
        utils.relative_url_for(request=request_mock, name="name")

    url_as_relative_mock.assert_called_once_with(
        origin_absolute_url="https://url/number/one",
        destination_absolute_url="https://url/number/one",
    )


@pytest.mark.parametrize(
    "header, version", [
        ('pip/23.0.1 {"installer":{"name":"pip","version":"23.0.1"}}', Version("23.0.1")),
        ('{"installer":{"name":"pip","version":"23.0.1"}}', Version("23.0.1")),
        ('', None),
        ('*/*', None),
        ('pip/23.0.1 {"installer":{"name":"pip","version":"AAA"}}', None),
    ],
)
def test_get_pip_version(header: str, version: Version | None) -> None:
    mock_request = mock.Mock(headers={"user-agent": header})
    utils.get_pip_version(mock_request) == version
