from configparser import ConfigParser
from json import loads
from pathlib import Path
from os import getenv


class SlsConfig:
    """Store all the configuration from the SousLeSens project"""

    def __init__(self, config_dir: Path):
        """Retrieve the configuration as JSON files from the config directory

        Parameters
        ----------
        config_dir : pathlib.Path
            The path to the SousLeSens config directory which contains the
            mainConfig.json and the other files
        """

        self.config_dir = config_dir

        self.mainconfig = self._get_sls_config("mainConfig.json")
        self.sources = self._get_sls_config("sources.json")
        self.profiles = self._get_sls_config("profiles.json")
        self.users = self._get_sls_config("users/users.json")

    def _get_sls_config(self, file_name: str) -> dict:
        """Read and parse the specified SousLeSens configuration file

        Parameters
        ----------
        file_name : str
            The name of the file contains in the SousLeSens config directory

        Returns
        -------
        dict
            The content of the JSON file as a Python dict structure
        """

        config_path = self.config_dir.joinpath(file_name)

        if not config_path.exists():
            raise FileNotFoundError(f"{file_name} connot be found in {config_path}")

        return loads(config_path.read_text())


class SlsConfigParser(ConfigParser):
    """Override the default parser to manage environment variables"""

    def _get_conv(
        self, section: str, option: str, conv: int | float | bool, *args, **kwargs
    ) -> int | float | bool:
        """Retrieve the value from environment or file and convert it

        Notes
        -----
        This method is use with getint, getfloat and getboolean

        Parameters
        ----------
        section : str
            The name of the section from the configuration file
        option : str
            The name of the option from the specified section
        conv : int or float or bool
            The Python type used to convert the variable

        Returns
        -------
        int or float or bool
            The value of the option convert with the specified Python type
        """

        variable = self._get_from_env(section, option)
        if variable is not None:
            return conv(variable)

        return super()._get_conv(section, option, conv, *args, **kwargs)

    def _get_from_env(self, section: str, option: str) -> str | None:
        """Retrieve the environment variable based on the specified option

        Parameters
        ----------
        section : str
            The name of the section from the configuration file
        option : str
            The name of the option from the specified section

        Returns
        -------
        str or None
            The environment variable if available, None otherwise
        """

        return getenv(f"{section.upper()}_{option.upper()}")

    def get(self, section: str, option: str, *args, **kwargs) -> str | None:
        """Retrieve the value from environment or file

        Parameters
        ----------
        section : str
            The name of the section from the configuration file
        option : str
            The name of the option from the specified section

        Returns
        -------
        str or None
            The environment variable if available, None otherwise
        """

        variable = self._get_from_env(section, option)
        if variable is not None:
            return variable

        return super().get(section, option, *args, **kwargs)
