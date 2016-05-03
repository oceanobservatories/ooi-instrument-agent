import logging

import zmq.green as zmq


log = logging.getLogger(__name__)
context = zmq.Context()


class TimeoutException(Exception):
    status_code = 408

    def __init__(self, message=None):
        Exception.__init__(self)
        self.message = message


class ZmqDriverClient(object):
    """
    A class for performing RPC with a ZMQ-based driver process

    Utilizes zmq.green to provide a gevent-compatible version of zmq
    """
    def __init__(self, host, port):
        """
        :param host: Hostname or IP of the target driver
        :param port: Port number of the target driver
        """
        self.host = host
        self.port = port
        log.debug('Start %r', self)

    def _connect(self):
        """
        :return: Connected ZMQ REQ socket
        """
        log.debug('Connecting ZMQ client: %r', self)
        socket = context.socket(zmq.REQ)
        socket.connect('tcp://{host}:{port}'.format(host=self.host, port=self.port))
        log.debug('Connected: %r', self)
        return socket

    def _command(self, command, *args, **kwargs):
        """
        :param command: RPC Command to execute
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return: Response from driver or empty dictionary if no response
        """
        socket = self._connect()
        with socket:
            log.debug('%r _command(%r %r %r)', self, command, args, kwargs)
            timeout = kwargs.pop('timeout', None)
            timeout = timeout if timeout is not None else 1000
            msg = {'cmd': command, 'args': args, 'kwargs': kwargs}
            socket.send_json(msg)
            events = socket.poll(timeout=timeout)
            if events:
                response = socket.recv_json()
                log.debug('%r _command RESPONSE: %r', self, response)
                return response
            raise TimeoutException({'timeout': 'no response in timeout interval %d' % timeout})

    def ping(self, *args, **kwargs):
        return self._command('process_echo', *args, **kwargs)

    def execute(self, command, *args, **kwargs):
        return self._command('execute_resource', command, *args, **kwargs)

    def init_params(self, *args, **kwargs):
        return self._command('set_init_params', *args, **kwargs)

    def shutdown(self, *args, **kwargs):
        return self._command('stop_driver_process', *args, **kwargs)

    def get_state(self, *args, **kwargs):
        return self._command('overall_state', *args, **kwargs)

    def get_resource(self, *args, **kwargs):
        return self._command('get_resource', *args, **kwargs)

    def set_resource(self, resource, *args, **kwargs):
        return self._command('set_resource', resource, *args, **kwargs)

    def discover(self, *args, **kwargs):
        return self._command('discover_state', *args, **kwargs)

    def set_log_level(self, *args, **kwargs):
        return self._command('set_log_level', *args, **kwargs)

    def __repr__(self):
        return 'ZmqDriverClient(%r, %r)' % (self.host, self.port)
