import typing

import fastapi
from fastapi.testclient import TestClient
import httpx
import pytest
from simple_repository import model
from simple_repository.components.core import SimpleRepository
from simple_repository.tests.components.fake_repository import FakeRepository

from simple_repository_server.routers import simple


def create_app(repo: SimpleRepository, repo_factory: typing.Callable[..., SimpleRepository]) -> fastapi.FastAPI:
    app = fastapi.FastAPI(openapi_url=None)

    http_client = httpx.AsyncClient()
    app.include_router(
        simple.build_router(
            repo,
            http_client=http_client,
            prefix="/snapshot/{cutoff_date}/",
            repo_factory=repo_factory,
        ),
    )

    return app


@pytest.fixture
def fake_repo() -> SimpleRepository:
    return FakeRepository(
        project_list=model.ProjectList(model.Meta("1.0"), [model.ProjectListElement("foo-bar")]),
        project_pages=[
            model.ProjectDetail(
                model.Meta('1.1'),
                "foo-bar",
                files=(
                    model.File("foo_bar-2.0-any.whl", "", {}, size=1),
                    model.File("foo_bar-3.0-any.whl", "", {}, size=1),
                ),
            ),
        ],
    )


@pytest.fixture
def empty_repo() -> SimpleRepository:
    return FakeRepository()


class SimpleFactoryWithParams:
    def __init__(self, repo: SimpleRepository):
        self.cutoff_date = None
        self.repo = repo

    def __call__(self, cutoff_date: str) -> SimpleRepository:
        self.cutoff_date = cutoff_date
        # In this factory, just return the original repo, but we return a
        # more specific repo here.
        return self.repo


@pytest.fixture
def repo_factory(fake_repo: SimpleRepository) -> SimpleFactoryWithParams:
    return SimpleFactoryWithParams(repo=fake_repo)


@pytest.mark.asyncio
async def test_repo_with_dependency_injection__projects_list(
        empty_repo: SimpleRepository,
        repo_factory: SimpleFactoryWithParams,
):
    app = create_app(empty_repo, repo_factory=repo_factory)
    client = TestClient(app)
    response = client.get("/snapshot/2020-10-12/?format=application/vnd.pypi.simple.v1+json")

    # Check that the factory was called with the expected args.
    assert repo_factory.cutoff_date == "2020-10-12"

    # And that the response is not for the empty repo, but the factory one.
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/vnd.pypi.simple.v1+json'
    assert response.json() == {
      "meta": {
        "api-version": "1.0",
      },
      "projects": [
        {
          "name": "foo-bar",
        },
      ],
    }


@pytest.mark.asyncio
async def test_repo_with_dependency_injection__project_page(
        empty_repo: SimpleRepository,
        repo_factory: SimpleFactoryWithParams,
):
    app = create_app(empty_repo, repo_factory=repo_factory)
    client = TestClient(app)
    response = client.get("/snapshot/2020-10-12/foo-bar/?format=application/vnd.pypi.simple.v1+json")

    # Check that the factory was called with the expected args.
    assert repo_factory.cutoff_date == "2020-10-12"

    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/vnd.pypi.simple.v1+json'

    response_data = response.json()
    expected_data = {
      "meta": {
        "api-version": "1.1",
      },
      "name": "foo-bar",
      "files": [
        {
          "filename": "foo_bar-2.0-any.whl",
          "url": "../../../resources/foo-bar/foo_bar-2.0-any.whl",
          "hashes": {},
          "size": 1,
        },
        {
          "filename": "foo_bar-3.0-any.whl",
          "url": "../../../resources/foo-bar/foo_bar-3.0-any.whl",
          "hashes": {},
          "size": 1,
        },
      ],
      "versions": [
        "2.0",
        "3.0",
      ],
    }

    # The version sort order is not currently deterministic, so test that separately.
    assert set(response_data.pop("versions")) == set(expected_data.pop("versions"))
    assert response_data == expected_data


@pytest.mark.asyncio
async def test_repo_with_dependency_injection__project_page__redirect(
        empty_repo: SimpleRepository,
        repo_factory: SimpleFactoryWithParams,
):
    app = create_app(empty_repo, repo_factory=repo_factory)
    client = TestClient(app)
    response = client.get(
        "/snapshot/2020-10-12/foo_Bar/?format=application/vnd.pypi.simple.v1+json",
        follow_redirects=False,
    )

    # Check that the factory was called with the expected args.
    assert repo_factory.cutoff_date == "2020-10-12"

    assert response.status_code == 301
    # Ensure that we maintain the querystring.
    assert response.headers['location'] == '../foo-bar/?format=application/vnd.pypi.simple.v1+json'
