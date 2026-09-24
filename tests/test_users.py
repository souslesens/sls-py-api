import pytest

from sls_api.users import User

DEFAULT_SOURCES = {
    "test_ro": {"accessControl": "read"},
    "test_rw": {"accessControl": "readwrite"},
}


@pytest.fixture
def default_values() -> dict:
    return {
        "groups": [],
        "id": "admin",
        "login": "admin",
        "allowSourceCreation": False,
        "maxNumberCreatedSource": 5,
    }


def test_create_user_with_valid_parameters(default_values):
    User(**default_values)


def test_create_user_with_missing_parameters(default_values):
    values = default_values.copy()
    del values["login"]

    with pytest.raises(TypeError):
        User(**values)


def test_default_user_is_admin(default_values):
    assert User(**default_values).is_admin() is True


def test_standard_user_is_not_admin(default_values):
    values = default_values.copy()
    values["login"] = "🍌"

    assert User(**values).is_admin() is False


def test_standard_user_with_admin_group_is_admin(default_values):
    values = default_values.copy()
    values["login"] = "🍅"
    values["groups"].append("admin")

    assert User(**values).is_admin() is True


def test_user_can_read(default_values):
    user = User(**default_values)
    user.set_sources(DEFAULT_SOURCES)

    for source in ("test_ro", "test_rw"):
        assert user.can_read(source) is True


def test_user_can_readwrite(default_values):
    user = User(**default_values)
    user.set_sources(DEFAULT_SOURCES)

    assert user.can_readwrite("test_ro") is False
    assert user.can_readwrite("test_rw") is True
