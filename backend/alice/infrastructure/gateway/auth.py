from __future__ import annotations

import http
from collections.abc import Callable

from .config import GatewayConfig


def extract_bearer_token(header_value: str | None) -> str:
    if not header_value:
        return ""
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def validate_bearer_token(header_value: str | None, expected_token: str) -> bool:
    if not expected_token:
        return True
    return extract_bearer_token(header_value) == expected_token


def build_process_request(config: GatewayConfig) -> Callable:
    def process_request(connection, request):
        authorization = request.headers.get("Authorization")
        if validate_bearer_token(authorization, config.token):
            return None
        return connection.respond(http.HTTPStatus.UNAUTHORIZED, "Unauthorized\n")

    return process_request


__all__ = ["extract_bearer_token", "validate_bearer_token", "build_process_request"]
