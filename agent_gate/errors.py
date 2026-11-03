"""Errors that come from the environment (network, API, quota), not from the agent's behaviour.

A run that hits one of these says nothing about the agent, so it is scored env_error, never as an
agent failure, and it never lets a check pass by default.
"""
import http.client
import socket
import urllib.error


class EnvError(Exception):
    """Raised by agents or providers when the model endpoint fails or returns a malformed response."""


ENV_EXCEPTIONS = (EnvError, urllib.error.URLError, http.client.HTTPException,
                  ConnectionError, TimeoutError, socket.timeout)


def is_env_error(e):
    return isinstance(e, ENV_EXCEPTIONS)
