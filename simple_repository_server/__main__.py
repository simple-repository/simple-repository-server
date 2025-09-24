# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import argparse
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import typing
from urllib.parse import urlparse

import fastapi
from fastapi import FastAPI
import httpx
from simple_repository.components.core import SimpleRepository
from simple_repository.components.http import HttpRepository
from simple_repository.components.local import LocalRepository
from simple_repository.components.metadata_injector import MetadataInjectorRepository
from simple_repository.components.priority_selected import PrioritySelectedProjectsRepository
import uvicorn

from simple_repository_server.routers import simple


def is_url(url: str) -> bool:
    return urlparse(url).scheme in ("http", "https")


def get_netrc_path() -> typing.Optional[Path]:
    """
    Get the netrc file path if it exists and is a regular file.
    Checks NETRC environment variable first, then ~/.netrc.
    Returns None if no valid netrc file is found.

    If NETRC is explicitly set but points to a non-existent or invalid file,
    returns None.
    """
    netrc_env = os.environ.get('NETRC')
    if netrc_env:
        netrc_path = Path(netrc_env)
        if netrc_path.exists() and netrc_path.is_file():
            return netrc_path
        # If NETRC is explicitly set but invalid, don't fall back to ~/.netrc
        return None

    default_netrc = Path.home() / '.netrc'
    if default_netrc.exists() and default_netrc.is_file():
        return default_netrc

    return None


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.description = "Run a Python Package Index"

    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--stream-http-resources",
        action="store_true",
        help="Stream HTTP resources through this server instead of redirecting (default: redirect)",
    )
    parser.add_argument(
        "repository_url", metavar="repository-url", type=str, nargs="+",
        help="Repository URL (http/https) or local directory path",
    )


def create_repository(
    repository_urls: list[str],
    *,
    http_client: httpx.AsyncClient,
) -> SimpleRepository:
    base_repos: list[SimpleRepository] = []
    repo: SimpleRepository
    for repo_url in repository_urls:
        if is_url(repo_url):
            repo = HttpRepository(
                url=repo_url,
                http_client=http_client,
            )
        else:
            repo = LocalRepository(
                index_path=Path(repo_url),
            )
        base_repos.append(repo)

    if len(base_repos) > 1:
        repo = PrioritySelectedProjectsRepository(base_repos)
    else:
        repo = base_repos[0]
    return MetadataInjectorRepository(repo, http_client)


def create_app(repository_urls: list[str], *, stream_http_resources: bool = False) -> fastapi.FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> typing.AsyncIterator[None]:
        # Configure httpx client with netrc support if netrc file exists
        netrc_path = get_netrc_path()
        auth: typing.Optional[httpx.Auth] = None
        if netrc_path:
            logging.info(f"Using netrc authentication from: {netrc_path}")
            auth = httpx.NetRCAuth(file=str(netrc_path))

        async with httpx.AsyncClient(auth=auth, follow_redirects=True) as http_client:
            repo = create_repository(repository_urls, http_client=http_client)
            app.include_router(
                simple.build_router(
                    repo,
                    http_client=http_client,
                    stream_http_resources=stream_http_resources,
                ),
            )
            yield

    app = FastAPI(
        openapi_url=None,  # Disables automatic OpenAPI documentation (Swagger & Redoc)
        lifespan=lifespan,
    )
    return app


def handler(args: typing.Any) -> None:
    host: str = args.host
    port: int = args.port
    repository_urls: list[str] = args.repository_url
    stream_http_resources: bool = args.stream_http_resources
    uvicorn.run(
        app=create_app(repository_urls, stream_http_resources=stream_http_resources),
        host=host,
        port=port,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    configure_parser(parser)
    args = parser.parse_args()
    handler(args)


if __name__ == '__main__':
    main()
