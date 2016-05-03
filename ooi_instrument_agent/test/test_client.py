import unittest
import mock
import zmq

from ooi_instrument_agent.client import ZmqDriverClient, TimeoutException


class ClientTest(unittest.TestCase):
    def setUp(self):
        pass

    def assert_rpc_call(self, mock_socket, method, command, args, kwargs, timeout=None, poll=True):
        instance = mock_socket.return_value
        instance.poll.return_value = poll

        client = ZmqDriverClient(None, None)
        client_method = getattr(client, method, None)
        if client_method is None:
            raise KeyError

        client_method(*args, timeout=timeout, **kwargs)

        instance.connect.assert_called_once_with('tcp://None:None')
        instance.poll.assert_called_once_with(timeout=timeout)

        expected_command = {
            'cmd': command,
            'args': args,
            'kwargs': kwargs
        }

        instance.send_json.assert_called_once_with(expected_command)

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_ping(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'ping', 'process_echo', tuple(), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_execute(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'execute', 'execute_resource',
                             ('DRIVER_EVENT_START_AUTOSAMPLE',), {}, timeout=90000)

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_no_response(self, mocked_socket):
        with self.assertRaises(TimeoutException):
            self.assert_rpc_call(mocked_socket, 'ping', 'process_echo', tuple(), {}, None, poll=False)

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_init_params(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'init_params', 'set_init_params', ({'parameters': {}},), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_shutdown(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'shutdown', 'stop_driver_process', tuple(), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_get_state(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'get_state', 'overall_state', tuple(), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_get_resource(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'get_resource', 'get_resource', ('DRIVER_PARAMETER_ALL',), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_set_resource(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'set_resource', 'set_resource', ({'param': 'value'},), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_get_discover(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'discover', 'discover_state', tuple(), {})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_set_log_level(self, mocked_socket):
        self.assert_rpc_call(mocked_socket, 'set_log_level', 'set_log_level', ('debug',), {})

    def test_client_repr(self):
        client = ZmqDriverClient(None, None)
        self.assertEqual(repr(client), 'ZmqDriverClient(None, None)')
