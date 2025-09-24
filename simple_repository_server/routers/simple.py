# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import functools
import hashlib
import typing

from fastapi import APIRouter, Depends, HTTPException
import fastapi.params
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
import httpx
import packaging.utils
import packaging.version
from simple_repository import SimpleRepository, content_negotiation, errors, model, serializer

from .. import utils
from .._http_response_iterator import HttpResponseIterator


def get_response_format(
        request: fastapi.Request,
        format: str | None = None,
) -> content_negotiation.Format:
    """
    A fastapi dependent which can optionally enable a PEP-691 format querystring,
    for example:

        /simple/some-project/?format=application/vnd.pypi.simple.v1+json

    """
    if format:
        # Allow the consumer to request a format as a query string such as
        # {URL}?format=application/vnd.pypi.simple.v1+json
        # Note: + in urls are interpreted as spaces by
        # urllib.parse.parse_qsl, used by FastAPI.
        requested_format = format.replace(" ", "+")
    else:
        requested_format = request.headers.get("Accept", "")

    try:
        response_format = content_negotiation.select_response_format(
            content_type=requested_format,
        )
    except errors.UnsupportedSerialization as e:
        raise HTTPException(status_code=406, detail=str(e))

    return response_format


def build_router(
    resource_repository: SimpleRepository,
    *,
    http_client: httpx.AsyncClient,
    prefix: str = "/simple/",
    repo_factory: typing.Optional[typing.Callable[..., SimpleRepository]] = None,
    stream_http_resources: bool = False,
) -> APIRouter:
    """
    Build a FastAPI router for the given repository and http_client.

    Note that for the simple end-points, the repository is an injected
    dependency, meaning that you can add your own dependencies into the repository
    (see the test_repo_dependency_injection for an example of this).

    """
    if not prefix.endswith("/"):
        raise ValueError("Prefix must end in '/'")

    if repo_factory is None:
        # If no repo factory is provided, use the same repository that we want to
        # use for resource handling.
        def repo_factory() -> SimpleRepository:
            return resource_repository

    simple_router = APIRouter(
        tags=["simple"],
        default_response_class=HTMLResponse,
    )
    #: To be fixed by https://github.com/tiangolo/fastapi/pull/2763
    get = functools.partial(simple_router.api_route, methods=["HEAD", "GET"])

    @get(prefix)
    async def project_list(
        response_format: typing.Annotated[content_negotiation.Format, Depends(get_response_format)],
        repository: typing.Annotated[SimpleRepository, Depends(repo_factory)],
    ) -> Response:
        project_list = await repository.get_project_list()

        serialized_project_list = serializer.serialize(
            page=project_list,
            format=response_format,
        )

        return Response(
            serialized_project_list,
            media_type=response_format.value,
        )

    @get(prefix + "{project_name}/")
    async def simple_project_page(
        request: fastapi.Request,
        project_name: str,
        repository: typing.Annotated[SimpleRepository, Depends(repo_factory)],
        response_format: typing.Annotated[content_negotiation.Format, Depends(get_response_format)],
    ) -> Response:
        normed_prj_name = packaging.utils.canonicalize_name(project_name)
        if normed_prj_name != project_name:
            # Update the original path params with the normed name.
            path_params = request.path_params | {'project_name': normed_prj_name}
            correct_url = utils.relative_url_for(
                request=request,
                name="simple_project_page",
                **path_params,
            )
            if request.url.query:
                correct_url = correct_url + "?" + request.url.query
            return RedirectResponse(
                url=correct_url,
                status_code=301,
            )

        try:
            package_releases = await repository.get_project_page(project_name)
        except errors.PackageNotFoundError as e:
            raise HTTPException(404, str(e))

        # Point all resource URLs to this router. The router may choose to redirect these
        # back to the original source, but this means that all resource requests go through
        # this server (it may be desirable to be able to disable this behaviour in the
        # future, though it would mean that there is the potential for a SimpleRepository
        # to have implemented a resource handler, yet it never sees the request).
        project_releases = utils.replace_urls(package_releases, project_name, request)

        serialized_project_page = serializer.serialize(
            page=project_releases,
            format=response_format,
        )
        return Response(
            serialized_project_page,
            media_type=response_format.value,
        )

    @get("/resources/{project_name}/{resource_name}")
    async def resources(
        request: fastapi.Request,
        resource_name: str,
        project_name: str,
    ) -> fastapi.Response:

        req_ctx = model.RequestContext(
            context=dict(request.headers.items()),
        )

        try:
            resource = await resource_repository.get_resource(
                project_name,
                resource_name,
                request_context=req_ctx,
            )
        except errors.ResourceUnavailable as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except errors.InvalidPackageError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        if isinstance(resource, model.TextResource):
            # Use the first 12 characters of the metadata digest as ETag
            text_hash = hashlib.sha256(resource.text.encode('UTF-8')).hexdigest()[:12]
            etag = f'"{text_hash}"'
            response_headers = {'ETag': etag}
            if etag == request.headers.get("if-none-match"):
                raise HTTPException(
                    304,
                    headers=response_headers,
                )
            return PlainTextResponse(
                content=resource.text,
                headers=response_headers,
            )

        if isinstance(resource, model.HttpResource):
            if stream_http_resources:
                response_iterator = await HttpResponseIterator.create_iterator(
                    http_client=http_client,
                    url=resource.url,
                    request_headers=request.headers,
                )
                return StreamingResponse(
                    content=response_iterator,
                    status_code=response_iterator.status_code,
                    headers=response_iterator.headers,
                )
            else:
                return RedirectResponse(url=resource.url, status_code=302)

        if isinstance(resource, model.LocalResource):
            ctx_etag = resource.context.get("etag")
            response_headers = {"ETag": ctx_etag} if ctx_etag else {}
            if client_etag := request.headers.get("if-none-match"):
                if client_etag == ctx_etag:
                    raise HTTPException(
                        304,
                        headers=response_headers,
                    )
            return FileResponse(
                path=resource.path,
                media_type="application/octet-stream",
                headers=response_headers,
            )

        raise ValueError("Unsupported resource type")

    return simple_router
