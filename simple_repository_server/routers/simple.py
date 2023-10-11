# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import functools
import hashlib

import aiohttp
from fastapi import APIRouter, HTTPException
import fastapi.params
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
import packaging.utils
import packaging.version
from simple_repository import SimpleRepository, content_negotiation, errors, model, serializer

from .. import utils
from ..http_response_iterator import HttpResponseIterator


def build_router(
    repository: SimpleRepository,
    streaming_session: aiohttp.ClientSession,
) -> APIRouter:
    simple_router = APIRouter(
        tags=["simple"],
        default_response_class=HTMLResponse,
    )
    #: To be fixed by https://github.com/tiangolo/fastapi/pull/2763
    get = functools.partial(simple_router.api_route, methods=["HEAD", "GET"])

    @get("/simple/")
    async def project_list(
        request: fastapi.Request,
        format: str | None = None,
    ) -> Response:
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

        project_list = await repository.get_project_list()

        serialized_project_list = serializer.serialize(
            page=project_list,
            format=response_format,
        )

        return Response(
            serialized_project_list,
            media_type=response_format.value,
        )

    @get("/simple/{package_name}/")
    async def simple_project_page(
        package_name: str,
        request: fastapi.Request,
        format: str | None = None,
    ) -> Response:
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

        try:
            package_releases = await repository.get_project_page(package_name)
        except errors.PackageNotFoundError as e:
            raise HTTPException(404, str(e))
        except errors.NotNormalizedProjectName:
            return RedirectResponse(
                url=utils.relative_url_for(
                    request=request,
                    name="simple_project_page",
                    package_name=packaging.utils.canonicalize_name(package_name),
                ),
            )

        package_releases = utils.replace_urls(package_releases, package_name, request)

        serialized_project_page = serializer.serialize(
            page=package_releases,
            format=response_format,
        )
        return Response(
            serialized_project_page,
            media_type=response_format.value,
        )

    @get("/resources/{package_name}/{resource_name}")
    async def resources(
        resource_name: str,
        package_name: str,
        request: fastapi.Request,
    ) -> fastapi.Response:
        try:
            resource = await repository.get_resource(package_name, resource_name)
        except errors.ResourceUnavailable as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except errors.InvalidPackageError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        if isinstance(resource, model.TextResource):
            # Use the first 12 characters of the metadata digest as ETag
            text_hash = hashlib.sha256(resource.text.encode('UTF-8')).hexdigest()[:12]
            if text_hash == request.headers.get("if-none-match"):
                raise HTTPException(304)
            return PlainTextResponse(
                content=resource.text,
                headers={'ETag': text_hash},
            )

        if isinstance(resource, model.HttpResource):
            response_iterator = await HttpResponseIterator.create_iterator(
                session=streaming_session,
                url=resource.url,
            )
            return StreamingResponse(
                content=response_iterator,
                status_code=response_iterator.status_code,
                headers=response_iterator.headers,
            )

        if isinstance(resource, model.LocalResource):
            etag = resource.context.get("etag")
            if client_etag := request.headers.get("if-none-match"):
                if client_etag == etag:
                    raise HTTPException(304)
            return FileResponse(
                path=resource.path,
                media_type="application/octet-stream",
                headers={"ETag": etag} if etag else {},
            )

        raise ValueError("Unsupported resource type")

    return simple_router
