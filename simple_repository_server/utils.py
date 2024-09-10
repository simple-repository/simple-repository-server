# Copyright (C) 2023, CERN
# This software is distributed under the terms of the MIT
# licence, copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from dataclasses import replace
import json
import re
import typing
from urllib.parse import urlparse

import fastapi
from packaging.version import InvalidVersion, Version
from simple_repository import model


def url_as_relative(
    destination_absolute_url: str,
    origin_absolute_url: str,
) -> str:
    """Converts, if possible, the destination_absolute_url to a relative to origin_absolute_url"""
    parsed_destination_url = urlparse(destination_absolute_url)
    parsed_origin_url = urlparse(origin_absolute_url)

    if (
        parsed_origin_url.scheme != parsed_destination_url.scheme or
        parsed_origin_url.scheme not in ["http", "https"] or
        parsed_origin_url.netloc != parsed_destination_url.netloc
    ):
        raise ValueError(
            "Cannot create a relative url from "
            f"{origin_absolute_url} to {destination_absolute_url}",
        )

    destination_absolute_path = parsed_destination_url.path
    origin_absolute_path = parsed_origin_url.path

    # Extract all the segments in the url contained between two "/"
    destination_path_tokens = destination_absolute_path.split("/")[1:-1]
    origin_path_tokens = origin_absolute_path.split("/")[1:-1]
    # Calculate the depth of the origin path. It will be the initial
    # number of  dirs to delete from the url to get the relative path.
    dirs_up = len(origin_path_tokens)

    common_prefix = "/"
    for destination_path_token, origin_path_token in zip(
            destination_path_tokens, origin_path_tokens,
    ):
        if destination_path_token == origin_path_token:
            # If the two urls share a parent dir, reduce the number of dirs to delete
            dirs_up -= 1
            common_prefix += destination_path_token + "/"
        else:
            break

    return "../" * dirs_up + destination_absolute_path.removeprefix(common_prefix)


def relative_url_for(
    request: fastapi.Request,
    name: str,
    **kwargs: typing.Any,
) -> str:
    origin_url = str(request.url)
    destination_url = str(request.url_for(name, **kwargs))

    return url_as_relative(
        origin_absolute_url=origin_url,
        destination_absolute_url=destination_url,
    )


def replace_urls(
    project_page: model.ProjectDetail,
    project_name: str,
    request: fastapi.Request,
) -> model.ProjectDetail:
    files = tuple(
        replace(
            file,
            url=relative_url_for(
                request=request,
                name="resources",
                project_name=project_name,
                resource_name=file.filename,
            ),
        ) for file in project_page.files
    )
    return replace(project_page, files=files)


PIP_HEADER_REGEX = re.compile(r'^.*?{')


def get_pip_version(
    request: fastapi.Request,
) -> Version | None:
    if not (pip_header_string := request.headers.get('user-agent', '')):
        return None
    pip_header = PIP_HEADER_REGEX.sub("{", pip_header_string)
    try:
        pip_info = json.loads(pip_header)
    except json.decoder.JSONDecodeError:
        return None
    if not isinstance(pip_info, dict):
        return None

    if implementation := pip_info.get('installer'):
        if isinstance(implementation, dict):
            version_string = implementation.get('version', '')
            try:
                return Version(version_string)
            except InvalidVersion:
                return None
    return None
