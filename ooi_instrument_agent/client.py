import logging

import zmq.green as zmq


DEFAULT_TIMEOUT = 10


log = logging.getLogger(__name__)


class ZmqDriverClient(object):
    """
    A class for communicating with a ZMQ-based driver process using python
    thread for catching asynchronous driver events.
    """
    def __init__(self, host, port):
        self.context = zmq.Context()
        self.host = host
        self.port = port
        log.debug('Start %r', self)
        self.socket = self._connect()

    def _connect(self):
        log.debug('Connecting ZMQ client: %r', self)
        socket = self.context.socket(zmq.REQ)
        socket.connect('tcp://{host}:{port}'.format(host=self.host, port=self.port))
        log.debug('Connected: %r', self)
        return socket

    def _command(self, command, *args, **kwargs):
        log.debug('%r _command(%r %r %r)', self, command, args, kwargs)
        timeout = kwargs.pop('timeout', 1000)
        msg = {'cmd': command, 'args': args, 'kwargs': kwargs}
        self.socket.send_json(msg)
        events = self.socket.poll(timeout=timeout)
        if events:
            response = self.socket.recv_json()
            log.debug('%r _command RESPONSE: %r', self, response)
            return response
        return {}

    def ping(self, *args, **kwargs):
        return self._command('process_echo', *args, **kwargs)

    def execute(self, command, **kwargs):
        return self._command('execute_resource', command, **kwargs)

    def init_params(self, *args, **kwargs):
        return self._command('set_init_params', *args, **kwargs)

    def shutdown(self, *args, **kwargs):
        return self._command('stop_driver_process', *args, **kwargs)

    def get_state(self, *args, **kwargs):
        return self._command('overall_state', *args, **kwargs)

    def get_resource(self, *args, **kwargs):
        return self._command('get_resource', *args, **kwargs)

    def set_resource(self, *args, **kwargs):
        return self._command('set_resource', *args, **kwargs)

    def discover(self, *args, **kwargs):
        return self._command('discover_state', *args, **kwargs)

    def set_log_level(self, *args, **kwargs):
        return self._command('set_log_level', *args, **kwargs)

    def __repr__(self):
        return 'ZmqDriverClient(%r, %r)' % (self.host, self.port)
