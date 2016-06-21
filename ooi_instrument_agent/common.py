import os

import datetime
from six import wraps

SOCK_ENV_KEY = 'SNIFF_UNIX_SOCKFILE'
DEFAULT_SOCKFILE = '/tmp/sniff.sock'


def get_sniffer_socket():
    return os.environ.get(SOCK_ENV_KEY, DEFAULT_SOCKFILE)


def stopwatch(logger):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            now = datetime.datetime.utcnow()
            result = func(*args, **kwargs)
            elapsed = datetime.datetime.utcnow() - now
            logger.error('%s took %s', func, elapsed)
            return result
        return inner
    return wrapper
