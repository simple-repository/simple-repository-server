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
  repository-url  Repository URL (http/https) or local directory path

options:
  -h, --help      show this help message and exit
  --port PORT
  --stream-http-resources
                  Stream HTTP resources through this server instead of redirecting (default: redirect)
```

The simplest example of this is to simply mirror the Python Package Index:

```bash
python -m simple_repository_server https://pypi.org/simple/
```

This will run a server (on port 8000 by default), you can then use it with `pip` or `uv` with the
appropriate configuration, for example:

```bash
export PIP_INDEX_URL=http://localhost:8000/simple/
pip install some-package-to-install
```

Or with `uv`:

```bash
export UV_INDEX_URL=http://localhost:8000/simple/
uv pip install some-package-to-install
```

## Server capabilities

If multiple repositories are provided to the CLI, the ``PrioritySelectedProjectsRepository`` component will be used to
combine them together in a way that mitigates the [dependency confusion attack](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610), with the first declared repository having the highest priority.

The server handles PEP-691 content negotiation to serve either HTML or JSON formats.
Per PEP-691, the default (fallback) content type is HTML, but a JSON response can
be previewed in the browser by adding the ``?format=application/vnd.pypi.simple.v1+json``
querystring to any of the repository URLs.

The server has been configured to include PEP-658 metadata, even if the upstream repository does
not include such metadata. This is done on the fly, and as a result the distribution will be
temporarily downloaded (in the case of http) to the server in order to extract and serve the metadata.

It is possible to use the resulting repository as input for the
[``simple-repository-browser``](https://github.com/simple-repository/simple-repository-browser), which
offers a web interface to browse and search packages in any simple package repository (PEP-503),
inspired by PyPI / warehouse.

It is expected that as new features appear in the underlying ``simple-repository`` library, those
which make general sense to enable by default will be introduced into the CLI without providing a
mechanism to disable those features. For more control, please see the "Non CLI usage" section.

## Repository sources

The server can work with both remote repositories and local directories:

```bash
# Remote repository
python -m simple_repository_server https://pypi.org/simple/

# Local directory
python -m simple_repository_server /path/to/local/packages/

# Multiple sources (priority order, local having precedence)
python -m simple_repository_server /path/to/local/packages/ https://pypi.org/simple/
```

Local directories should be organised with each project in its own subdirectory using the
canonical package name (lowercase, with hyphens instead of underscores):

```
/path/to/local/packages/
├── my-package/
│   ├── my_package-1.0.0-py3-none-any.whl
│   └── my-package-1.0.0.tar.gz
└── another-package/
    └── another_package-2.1.0-py3-none-any.whl
```

If metadata files are in the local repository they will be served directly, otherwise they
will be extracted on-the-fly and served.

## Authentication

The server automatically supports netrc-based authentication for private http repositories.
If a `.netrc` file exists in your home directory or is specified via the `NETRC` environment
variable, the server will use those credentials when accessing HTTP repositories.

## Resource handling

By default, HTTP resource requests (e.g. wheel downloads) are redirected to their original URLs
(302 redirect).
To stream resources through the server instead, use the `--stream-http-resources` CLI flag.

**Redirecting (default) is suitable for:**
- Most public repository scenarios
- When bandwidth and server processing overhead are considerations

**Streaming is useful for:**
- Air-gapped environments where clients cannot access upstream URLs directly
- When the server has authentication credentials that clients lack

## Non CLI usage

This project provides a number of tools in order to build a repository service using FastAPI.
For cases when control of the repository configuration is required, and where details of the
ASGI environment need more precise control, it is expected that ``simple-repository-server`` is used
as a library instead of a CLI.

Currently, the API for this functionality is under development, and will certainly change in the
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
