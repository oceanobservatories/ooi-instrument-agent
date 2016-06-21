import logging

import six
import zmq.green as zmq


log = logging.getLogger(__name__)
context = zmq.Context()
DEFAULT_TIMEOUT = 60


class TimeoutException(Exception):
    status_code = 408

    def __init__(self, message=None):
        Exception.__init__(self)
        self.message = message


class ParameterException(Exception):
    status_code = 400

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
        self._socket = None
        log.debug('Start %r', self)

    def _connect(self):
        """
        :return: Connected ZMQ REQ socket
        """
        if self._socket is None:
            log.debug('Connecting ZMQ client: %r', self)
            socket = context.socket(zmq.REQ)
            socket.connect('tcp://{host}:{port}'.format(host=self.host, port=self.port))
            log.debug('Connected: %r', self)
            self._socket = socket
        return self._socket

    def _command(self, command, *args, **kwargs):
        """
        :param command: RPC Command to execute
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return Response from driver
        :raises TimeoutException if no response received before timeout milliseconds
        """
        socket = self._connect()
        log.debug('%r _command(%r %r %r)', self, command, args, kwargs)
        timeout = kwargs.pop('timeout', None)
        timeout = timeout if timeout is not None else 1000
        msg = {'cmd': command, 'args': args, 'kwargs': kwargs}
        socket.send_json(msg)
        events = socket.poll(timeout=timeout)
        if events:
            response = socket.recv_json()
            return response
        raise TimeoutException({'timeout': 'no response in timeout interval %d' % timeout})

    def __enter__(self):
        """Client as context manager"""
        return self

    def __exit__(self, *args, **kwargs):
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def ping(self, *args, **kwargs):
        return self._command('process_echo', *args, **kwargs)

    def execute(self, command, *args, **kwargs):
        timeout = kwargs.pop('timeout', None)
        if timeout is None:
            state = self.get_state()
            timeout = _get_timeout(command, state)
        kwargs['timeout'] = timeout
        return self._command('execute_resource', command, *args, **kwargs)

    def init_params(self, *args, **kwargs):
        return self._command('set_init_params', *args, **kwargs)

    def shutdown(self, *args, **kwargs):
        return self._command('stop_driver_process', *args, **kwargs)

    def get_state(self, *args, **kwargs):
        return self._command('overall_state', *args, **kwargs)

    def get_resource_state(self, *args, **kwargs):
        return self._command('get_resource_state', *args, **kwargs)

    def get_resource(self, *args, **kwargs):
        return self._command('get_resource', *args, **kwargs)

    def set_resource(self, resource, *args, **kwargs):
        state = self.get_state()
        parameter_metadata = _get_parameters(state)

        timeout = kwargs.pop('timeout')
        if timeout is None:
            timeout = _get_timeout('DRIVER_EVENT_SET', state)
        kwargs['timeout'] = timeout

        resource = _validate_parameters(parameter_metadata, resource)

        return self._command('set_resource', resource, *args, **kwargs)

    def discover(self, *args, **kwargs):
        return self.execute('DRIVER_EVENT_DISCOVER', *args, **kwargs)

    def set_log_level(self, *args, **kwargs):
        return self._command('set_log_level', *args, **kwargs)

    def __repr__(self):
        return 'ZmqDriverClient(%r, %r)' % (self.host, self.port)


def _get_timeout(command, state_response):
    commands = state_response.get('value', {}).get('metadata', {}).get('commands', {})
    return commands.get(command, {}).get('timeout', DEFAULT_TIMEOUT) * 1000


def _get_parameters(state_response):
    return state_response.get('value', {}).get('metadata', {}).get('parameters', {})


def _is_writable(parameter, parameter_metadata):
    return parameter_metadata.get(parameter, {}).get('visibility') == 'READ_WRITE'


def _get_range_ptype(parameter, parameter_metadata):
    prange = parameter_metadata.get(parameter, {}).get('range')
    ptype = parameter_metadata.get(parameter, {}).get('value', {}).get('type')
    return prange, ptype


def _coerce_type(value, ptype):
    if ptype == 'string':
        if isinstance(value, basestring):
            return value
        try:
            return str(value)
        except:
            return None

    if ptype == 'bool':
        if isinstance(value, bool):
            return value
        elif isinstance(value, int):
            if value == 0:
                return False
            if value == 1:
                return True
        elif isinstance(value, basestring):
            if value in ['true', 'True']:
                return True
            if value in ['false', 'False']:
                return False

    if ptype == 'int':
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, basestring):
            try:
                return int(value)
            except ValueError:
                return None

    if ptype == 'float':
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if isinstance(value, basestring):
            try:
                return float(value)
            except ValueError:
                return None


def _validate_parameters(parameter_metadata, parameters):
    errors = {}
    out = {}
    for parameter, value in six.iteritems(parameters):
        if not _is_writable(parameter, parameter_metadata):
            errors[parameter] = 'Parameter(%s) not writeable' % parameter
            continue

        prange, ptype = _get_range_ptype(parameter, parameter_metadata)
        new_value = _coerce_type(value, ptype)
        if new_value is None:
            errors[parameter] = 'Parameter(%s) Unable to coerce to %s (%s)' % (parameter, ptype, value)
            continue

        if prange is not None:
            if isinstance(prange, list):
                if new_value < prange[0] or new_value > prange[-1]:
                    errors[parameter] = 'Parameter(%s) outside valid range (%r) (%r)' % (parameter, prange, value)
                    continue
            elif isinstance(prange, dict):
                if new_value not in prange.values():
                    errors[parameter] = 'Parameter(%s) not one of (%r) (%r)' % (parameter, prange.values(), value)
                    continue

        out[parameter] = new_value

    if errors:
        raise ParameterException(errors)

    return out
