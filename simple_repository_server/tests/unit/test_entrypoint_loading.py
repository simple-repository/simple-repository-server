# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from pathlib import Path
from unittest import mock

import httpx
import pytest
from simple_repository.components.core import SimpleRepository
from simple_repository.components.http import HttpRepository
from simple_repository.components.local import LocalRepository

from simple_repository_server.__main__ import load_repository_from_spec

repo_dir = Path(__file__).parent


def _test_repo_factory() -> SimpleRepository:
    # Test helper: factory function that returns a repository
    return LocalRepository(index_path=repo_dir)


@pytest.fixture
def http_client():
    return mock.Mock(spec=httpx.AsyncClient)


def test_load_http_url(http_client):
    """HTTP URLs should create HttpRepository"""
    repo = load_repository_from_spec("https://pypi.org/simple/", http_client=http_client)
    assert isinstance(repo, HttpRepository)
    assert repo._source_url == "https://pypi.org/simple/"


def test_load_existing_path(tmp_path, http_client):
    """Existing directory paths should create LocalRepository"""
    test_dir = tmp_path / "packages"
    test_dir.mkdir()

    repo = load_repository_from_spec(str(test_dir), http_client=http_client)
    assert isinstance(repo, LocalRepository)
    assert repo._index_path == test_dir


def test_load_entrypoint(http_client):
    """Entrypoint spec should load and call the factory"""
    spec = "simple_repository_server.tests.unit.test_entrypoint_loading:_test_repo_factory"
    repo = load_repository_from_spec(spec, http_client=http_client)
    assert isinstance(repo, LocalRepository)
    assert repo._index_path == repo_dir
