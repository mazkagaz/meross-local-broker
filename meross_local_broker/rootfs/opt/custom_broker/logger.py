"""Loggers setup and utilities"""
import logging
import os
import sys


_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

logging.basicConfig(format='%(levelname)s:%(message)s', level=_LEVEL, stream=sys.stdout)


def get_logger(name: str):
    """Returns the a logger for the specific name and creates a new one if not available yet"""
    return logging.getLogger(name)


def set_logger_level(level):
    """Configures the root logging level"""
    logging.getLogger().setLevel(level)
