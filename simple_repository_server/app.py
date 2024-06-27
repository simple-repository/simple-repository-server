# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from contextlib import asynccontextmanager
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

from .routers import simple


def is_url(url: str) -> bool:
    return urlparse(url).scheme in ("http", "https")


def create_repository(
    repository_urls: list[str],
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


def create_app(repository_urls: list[str]) -> fastapi.FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> typing.AsyncIterator[None]:
        # If trust_env is set, httpx will use the url specified in the HTTP(S)_PROXY
        # env var as http proxy for all the connections created from this session.
        http_client = httpx.AsyncClient(trust_env=True)
        repo = create_repository(repository_urls, http_client)
        app.include_router(simple.build_router(repo, http_client), prefix="")
        yield
        await http_client.aclose()

    app = FastAPI(
        openapi_url=None,  # Disables automatic OpenAPI documentation (Swagger & Redoc)
        lifespan=lifespan,
    )
    return app
