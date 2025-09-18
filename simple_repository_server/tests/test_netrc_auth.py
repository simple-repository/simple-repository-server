from pathlib import Path
import textwrap
from unittest import mock

from fastapi.testclient import TestClient
import httpx
import pytest

from simple_repository_server.__main__ import create_app, get_netrc_path


@pytest.fixture
def netrc_file(tmp_path: Path) -> Path:
    """Create a temporary netrc file for testing."""
    netrc = tmp_path / 'my-netrc'
    netrc.write_text(
        textwrap.dedent("""\n
        machine gitlab.example.com
        login deploy-token-123
        password glpat-xxxxxxxxxxxxxxxxxxxx
    """),
    )
    return netrc


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    homedir = tmp_path / 'my-home'
    homedir.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: homedir)
    return homedir


def test_get_netrc__path_not_in_home(tmp_home: Path, netrc_file: Path):
    """Test get_netrc_path returns None when no netrc file exists."""
    result = get_netrc_path()
    assert result is None


def test_get_netrc__path_in_home(tmp_home: Path, netrc_file: Path):
    """Test get_netrc_path returns None when no netrc file exists."""
    home_netrc = tmp_home / '.netrc'
    netrc_file.rename(home_netrc)
    result = get_netrc_path()
    assert result == home_netrc


def test_get_netrc__netrc_env_var(netrc_file: Path, monkeypatch: pytest.MonkeyPatch):
    """Test get_netrc_path uses NETRC environment variable when file exists."""
    monkeypatch.setenv('NETRC', str(netrc_file))
    result = get_netrc_path()
    assert result == netrc_file


def test_get_netrc__netrc_env_var_nonexistent(tmp_home: Path, netrc_file: Path, monkeypatch: pytest.MonkeyPatch):
    """Test get_netrc_path returns None when NETRC points to non-existent file (no fallback)."""
    # Create ~/.netrc in home directory
    home_netrc = tmp_home / '.netrc'
    netrc_file.rename(home_netrc)

    # Set NETRC to non-existent file
    monkeypatch.setenv('NETRC', str(tmp_home / 'doesnt_exist'))
    result = get_netrc_path()

    # Should return None, NOT fall back to ~/.netrc
    assert result is None


def test_create_app__with_netrc(netrc_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('NETRC', str(netrc_file))
    with mock.patch(
            'simple_repository_server.__main__.create_repository',
    ) as mock_create_repository:
        app = create_app(["https://gitlab.example.com/simple/"])

        # Create a test client which will trigger the lifespan context
        with TestClient(app):
            pass

        # Verify create_repository was called
        assert mock_create_repository.called
        args, kwargs = mock_create_repository.call_args

        http_client = kwargs['http_client']

        # Verify it's an AsyncClient with NetRCAuth
        assert isinstance(http_client, httpx.AsyncClient)
        assert http_client._auth is not None
        assert isinstance(http_client._auth, httpx.NetRCAuth)
