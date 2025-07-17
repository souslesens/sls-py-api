from json.decoder import JSONDecodeError
from pathlib import Path
from shutil import rmtree
from tempfile import gettempdir
from unittest import TestCase
from unittest.mock import patch

from sls_api.config import SlsConfigParser


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
