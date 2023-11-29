from copy import deepcopy
from unittest import TestCase

from sls_api.users import User


class TestUser(TestCase):
    DEFAULT_VALUES = {
        "_type": "user",
        "groups": [],
        "id": "admin",
        "login": "admin",
        "name": "admin",
        "password": "admin",
        "source": "admin",
        "token": "admin",
    }

    DEFAULT_SOURCES = {
        "test_ro": {"accessControl": "read"},
        "test_rw": {"accessControl": "readwrite"},
    }

    def test_create_user_with_valid_parameters(self):
        User(**self.DEFAULT_VALUES)

    def test_create_user_with_missing_parameters(self):
        values = deepcopy(self.DEFAULT_VALUES)
        del values["login"]

        with self.assertRaises(TypeError):
            User(**values)

    def test_default_user_is_admin(self):
        user = User(**self.DEFAULT_VALUES)
        self.assertTrue(user.is_admin())

    def test_standard_user_is_not_admin(self):
        values = deepcopy(self.DEFAULT_VALUES)
        values["name"] = "🍌"

        user = User(**values)
        self.assertFalse(user.is_admin())

    def test_standard_user_is_admin(self):
        values = deepcopy(self.DEFAULT_VALUES)
        values["name"] = "🍅"
        values["groups"].append("admin")

        user = User(**values)
        self.assertTrue(user.is_admin())

    def test_user_can_read(self):
        user = User(**self.DEFAULT_VALUES)
        user.set_sources(self.DEFAULT_SOURCES)

        for source in ("test_ro", "test_rw"):
            self.assertTrue(user.can_read(source))

    def test_user_can_readwrite(self):
        user = User(**self.DEFAULT_VALUES)
        user.set_sources(self.DEFAULT_SOURCES)

        self.assertFalse(user.can_readwrite("test_ro"))
        self.assertTrue(user.can_readwrite("test_rw"))
