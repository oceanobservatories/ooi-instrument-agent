import os

SOCK_ENV_KEY = 'SNIFF_UNIX_SOCKFILE'
DEFAULT_SOCKFILE = '/tmp/sniff.sock'


def get_sniffer_socket():
    return os.environ.get(SOCK_ENV_KEY, DEFAULT_SOCKFILE)