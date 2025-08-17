import pytest

from fast_room_api.api.routers.auth import sanitize_username


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SimpleUser", "simpleuser"),
        ("User__Name", "user_name"),
        ("Weird--Name", "weird_name"),
        ("   Mixed  Spaces  ", "mixed_spaces"),
        ("UPPER_and-lower", "upper_and_lower"),
    ],
)
def test_sanitize_username_valid(raw, expected):
    assert sanitize_username(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["!!!!", "***", "????", "   ", "__--__"],
)
def test_sanitize_username_invalid(raw):
    with pytest.raises(ValueError):
        sanitize_username(raw)
