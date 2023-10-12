# simple-repository-server

A tool for running a PEP-503 simple Python package repository, including features such as dist metadata (PEP-658) and JSON API (PEP-691)

## Installation

```bash
python -m pip install simple-repository-server
```

## Usage

The ``simple-repository-server`` is designed to be used as a library, but also includes a convenient command line interface for running
a simple repository service:

```bash
$ simple-repository-server --help
usage: simple-repository-server [-h] [--port PORT] repository-url [repository-url ...]

Run a Simple Repository Server

positional arguments:
  repository-url

options:
  -h, --help      show this help message and exit
  --port PORT
```

If multiple repositories are provided, the ``PrioritySelectedProjectsRepository`` component will be used to
combine them together in a way that mitigates the [dependency confusion attack](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610).

The server handles PEP-691 content negotiation to serve either HTML or JSON formats.
Per PEP-691, the default (fallback) content type is HTML, but a JSON response can
be previewed in the browser by adding the ``?format=application/vnd.pypi.simple.v1+json``
querystring to any of the repository URLs.

The server has been configured to include PEP-658 metadata, even if the upstream repository does
not include such metadata. This is done on the fly, and as a result the distribution will be
temporarily downloaded to the server in order to extract and serve the metadata.

It is possible to use the resulting repository as input for the
[``simple-repository-browser``](https://github.com/simple-repository/simple-repository-browser), which
offers a web interface to browse and search packages in any simple package repository (PEP-503),
inspired by PyPI / warehouse.

It is expected that as new features appear in the underlying ``simple-repository`` library, those
which make general sense to enable by default will be introduced into the CLI without providing a
mechanism to disable those features. For more control, please see the "Non CLI usage" section.

## Non CLI usage

This project provides a number of tools in order to build a repository service using FastAPI.
For cases when control of the repository configuration is required, and where details of the
ASGI environment need more precise control, it is expected that ``simple-repository-server`` is used
as a library instead of a CLI.

Currently the API for this functionality is under development, and will certainly change in the
future.

## License and Support

This code has been released under the MIT license.
It is an initial prototype which is developed in-house, and _not_ currently openly developed.

It is hoped that the release of this prototype will trigger interest from other parties that have similar needs.
With sufficient collaborative interest there is the potential for the project to be openly
developed, and to power Python package repositories across many domains.

Please get in touch at https://github.com/orgs/simple-repository/discussions to share how
this project may be useful to you. This will help us to gauge the level of interest and
provide valuable insight when deciding whether to commit future resources to the project.
