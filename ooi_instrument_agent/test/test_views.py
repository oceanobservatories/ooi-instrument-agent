import json
import unittest

import mock
import ooi_instrument_agent
from ooi_instrument_agent.lock import Locked
from ooi_instrument_agent.test.responses import health_response
from ooi_instrument_agent.views import lockout


class ViewTest(unittest.TestCase):
    def setUp(self):
        ooi_instrument_agent.app.config['TESTING'] = True
        self.app = ooi_instrument_agent.app.test_client()
        self.instruments = ["RS10ENGC-XX00X-00-SPKIRA001", "RS10ENGC-XX00X-00-TMPSFA001"]

    def tearDown(self):
        pass

    @mock.patch('ooi_instrument_agent.views.Consul')
    def test_list_drivers(self, consul_mock):
        # mock the response from Consul
        instance = consul_mock.return_value
        instance.health.service.return_value = 1, json.loads(health_response)

        # make the request
        rv = self.app.get('instrument/api')

        # validate the response is JSON
        self.assertEqual(rv.content_type, 'application/json')

        # validate the response
        data = json.loads(rv.data)
        self.assertEqual(data, ["RS10ENGC-XX00X-00-SPKIRA001", "RS10ENGC-XX00X-00-TMPSFA001"])

    @mock.patch('ooi_instrument_agent.utils.ZmqDriverClient')
    @mock.patch('ooi_instrument_agent.views.Consul')
    def test_ping(self, consul_mock, client_mock):
        mock_response = {'response': 'PONG'}
        # mock the response from Consul
        instance = consul_mock.return_value
        instance.health.service.return_value = 1, json.loads(health_response)

        # mock the response from Zmq
        instance = client_mock.return_value
        instance.ping.return_value = mock_response

        rv = self.app.get('instrument/api/RS10ENGC-XX00X-00-SPKIRA001/ping')
        # validate the response is JSON
        self.assertEqual(rv.content_type, 'application/json')

        # validate the response
        data = json.loads(rv.data)
        self.assertEqual(data, mock_response)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_lockout(self, consul_mock):
        locker = 'unittest'
        backing_dict = {}

        def getitem(name):
            return backing_dict.get(name)

        def setitem(name, value):
            backing_dict[name] = value

        lock_mock = mock.MagicMock()
        lock_mock.__getitem__.side_effect = getitem
        lock_mock.__setitem__.side_effect = setitem

        ooi_instrument_agent.views.page.lock_manager = lock_mock

        @lockout
        def inner(driver_id=None):
            return

        # First, without a lock
        inner(driver_id=locker)

        # now, lock it and test
        lock_mock[locker] = locker
        with self.assertRaises(Locked):
            inner(driver_id=locker)