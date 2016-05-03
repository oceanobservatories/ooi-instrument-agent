import unittest
import mock
import zmq

from ooi_instrument_agent.client import ZmqDriverClient

ping_response = 'PONG'
execute_response = 'EXECUTED'


class ClientTest(unittest.TestCase):
    def setUp(self):
        pass

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_ping(self, mocked):
        instance = mocked.return_value
        instance.recv_json.return_value = ping_response

        pong = ZmqDriverClient(None, None).ping()
        self.assertEqual(pong, ping_response)

        instance.connect.assert_called_once_with('tcp://None:None')
        instance.poll.assert_called_once_with(timeout=1000)
        instance.send_json.assert_called_once_with({'cmd': 'process_echo', 'args': (), 'kwargs': {}})

    @mock.patch('ooi_instrument_agent.client.zmq._Context._socket_class', autospec=zmq.sugar.Socket)
    def test_execute(self, mocked):
        instance = mocked.return_value
        instance.recv_json.return_value = execute_response

        resp = ZmqDriverClient(None, None).execute('DRIVER_EVENT_START_AUTOSAMPLE', timeout=90000)
        self.assertEqual(resp, execute_response)

        instance.connect.assert_called_once_with('tcp://None:None')
        instance.poll.assert_called_once_with(timeout=90000)
        instance.send_json.assert_called_once_with({'cmd': 'execute_resource',
                                                    'args': ('DRIVER_EVENT_START_AUTOSAMPLE',), 'kwargs': {}})