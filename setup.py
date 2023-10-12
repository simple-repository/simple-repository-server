# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent.absolute()
with (HERE / "README.md").open("rt") as fh:
    LONG_DESCRIPTION = fh.read().strip()

REQUIREMENTS: dict[str, list[str]] = {
    "core": [
        "aiohttp",
        "aiosqlite",
        "fastapi>=0.100.0",
        "gunicorn",
        "packaging",
        "uvicorn[standard]",
        "pydantic-settings",
        "simple-repository",
    ],
    "test": [
        # httpx is needed for starlette.TestClient. https://www.starlette.io/#dependencies
        "httpx>=0.25",
        "pytest",
        "pytest_asyncio",
        "starlette>=0.26.1",
    ],
    "dev": [
        "pre-commit",
    ],
}

setup(
    name="simple-repository-server",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="BE-CSS-SET, CERN",
    url="https://github.com/simple-repository/simple-repository-server",
    packages=find_packages(),
    entry_points={'console_scripts': ['simple-repository-server = simple_repository_server.__main__:main']},
    python_requires="~=3.11",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "Framework :: FastAPI",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    install_requires=REQUIREMENTS["core"],
    extras_require={
        **REQUIREMENTS,
        # The "dev" extra is the union of "test" and "doc", with an option
        # to have explicit development dependencies listed.
        "dev": [
            req
            for extra in ["dev", "test", "doc"]
            for req in REQUIREMENTS.get(extra, [])
        ],
        # The "all" extra is the union of all requirements.
        "all": [req for reqs in REQUIREMENTS.values() for req in reqs],
    },
)
