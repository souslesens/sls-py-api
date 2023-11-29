from configparser import ConfigParser
from os import getenv


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
