import logging
from colorlog import ColoredFormatter

levels = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def log(level):
    LOG_LEVEL = levels.get(level.lower(), logging.INFO)
    LOGFORMAT = "%(log_color)s%(levelname)s%(reset)s: %(message)8s"

    logging.root.setLevel(LOG_LEVEL)
    formatter = ColoredFormatter(LOGFORMAT)
    stream = logging.StreamHandler()
    stream.setLevel(LOG_LEVEL)
    stream.setFormatter(formatter)
    log = logging.getLogger()
    log.setLevel(LOG_LEVEL)
    log.addHandler(stream)
    return log
