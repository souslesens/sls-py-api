from unittest.mock import patch

import pytest

from sls_api.config import SlsConfigParser

VARIABLES = {
    "TEST_ANIMAL": "🐈",
    "TEST_AGE": "10",
    "TEST_IS_CUTE": "no",
}


@pytest.fixture
def parser() -> SlsConfigParser:
    parser = SlsConfigParser()
    parser.add_section("test")
    parser.set("test", "animal", "🦆")
    parser.set("test", "age", "42")
    parser.set("test", "size", "13.37")
    parser.set("test", "is_cute", "yes")
    return parser


def test_configparser_convert_from_config(parser):
    assert parser.get("test", "animal") == "🦆"
    assert parser.getint("test", "age") == 42
    assert parser.getfloat("test", "size") == 13.37
    assert parser.getboolean("test", "is_cute") is True


def test_configparser_convert_from_environment(parser):
    with patch.dict("os.environ", VARIABLES):
        assert parser.get("test", "animal") == "🐈"
        assert parser.getint("test", "age") == 10
        assert parser.getboolean("test", "is_cute") is False


def test_get_returns_file_value_when_no_env_var(parser):
    assert parser.get("test", "animal") == "🦆"
