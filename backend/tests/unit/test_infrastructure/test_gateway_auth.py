import pytest

from backend.alice.infrastructure.gateway.auth import extract_bearer_token, validate_bearer_token


@pytest.mark.unit
def test_extract_bearer_token_returns_token_for_valid_header() -> None:
    assert extract_bearer_token("Bearer secret-token") == "secret-token"


@pytest.mark.unit
def test_extract_bearer_token_rejects_invalid_scheme() -> None:
    assert extract_bearer_token("Basic abc") == ""


@pytest.mark.unit
def test_validate_bearer_token_accepts_matching_token() -> None:
    assert validate_bearer_token("Bearer secret-token", "secret-token") is True


@pytest.mark.unit
def test_validate_bearer_token_rejects_mismatch() -> None:
    assert validate_bearer_token("Bearer wrong", "secret-token") is False


@pytest.mark.unit
def test_validate_bearer_token_allows_when_gateway_token_unset() -> None:
    assert validate_bearer_token(None, "") is True
