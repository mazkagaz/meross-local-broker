# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
"""Loggers setup and utilities"""
import logging
import os
import sys

from log_redaction import install_filter, install_handlers


_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

logging.basicConfig(format='%(levelname)s:%(message)s', level=_LEVEL, stream=sys.stdout)
install_handlers(logging.getLogger().handlers)


def get_logger(name: str):
    """Returns the a logger for the specific name and creates a new one if not available yet"""
    logger = logging.getLogger(name)
    install_filter(logger)
    return logger


def set_logger_level(level):
    """Configures the root logging level"""
    logging.getLogger().setLevel(level)
