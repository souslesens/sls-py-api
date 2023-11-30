from json.decoder import JSONDecodeError
from pathlib import Path
from shutil import rmtree
from tempfile import gettempdir
from unittest import TestCase
from unittest.mock import patch

from sls_api.config import SlsConfig, SlsConfigParser


class TestSlsConfig(TestCase):
    def setUp(self):
        self.path = Path(gettempdir()).joinpath("sls_api_test")
        self.path.mkdir(mode=0o755, exist_ok=False)

    def tearDown(self):
        if self.path.exists():
            rmtree(self.path)

    def test_construct_config_with_missing_files(self):
        mainconfig = self.path.joinpath("mainConfig.json")
        mainconfig.write_text("{}")

        with self.assertRaises(FileNotFoundError):
            SlsConfig(self.path)

    def test_construct_config_with_empty_files(self):
        mainconfig = self.path.joinpath("mainConfig.json")
        mainconfig.touch()

        with self.assertRaises(JSONDecodeError):
            SlsConfig(self.path)

    def test_construct_config(self):
        for filename in ("mainConfig", "sources", "profiles"):
            config = self.path.joinpath(f"{filename}.json")
            config.write_text("{}")

        users = self.path.joinpath("users")
        users.mkdir()
        users.joinpath("users.json").write_text("{}")

        SlsConfig(self.path)


class TestSlsConfigParser(TestCase):
    VARIABLES = {
        "TEST_ANIMAL": "🐈",
        "TEST_AGE": "10",
        "TEST_IS_CUTE": "no",
    }

    def setUp(self):
        self.parser = SlsConfigParser()
        self.parser.add_section("test")
        self.parser.set("test", "animal", "🦆")
        self.parser.set("test", "age", "42")
        self.parser.set("test", "size", "13.37")
        self.parser.set("test", "is-cute", "yes")

    def test_configparser_convert_from_config(self):
        self.assertEqual(self.parser.get("test", "animal"), "🦆")
        self.assertEqual(self.parser.getint("test", "age"), 42)
        self.assertTrue(self.parser.getfloat("test", "size"), 13.37)
        self.assertTrue(self.parser.getboolean("test", "is-cute"))

    def test_configparser_convert_from_envion(self):
        with patch.dict("os.environ", self.VARIABLES):
            self.assertEqual(self.parser.get("test", "animal"), "🐈")
            self.assertEqual(self.parser.getint("test", "age"), 10)
            self.assertTrue(self.parser.getboolean("test", "is-cute"))
