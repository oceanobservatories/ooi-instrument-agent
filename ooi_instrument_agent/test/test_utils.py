import json
import unittest

import mock
from consul import Consul
from werkzeug.exceptions import NotFound

from ooi_instrument_agent.client import ZmqDriverClient
from ooi_instrument_agent.test.responses import health_response, port_agent_response
from ooi_instrument_agent.utils import (list_drivers, get_client, get_host_and_port, get_service_host_and_port,
                                        get_port_agent, get_from_request, get_timeout)


class UtilsTest(unittest.TestCase):
    def test_list_drivers(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, json.loads(health_response))

        result = list_drivers(consul_mock)
        self.assertEqual(result, ["RS10ENGC-XX00X-00-SPKIRA001", "RS10ENGC-XX00X-00-TMPSFA001"])

    def test_list_drivers_empty(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, [])

        result = list_drivers(consul_mock)
        self.assertEqual(result, [])

    def test_get_client(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, json.loads(health_response))

        result = get_client(consul_mock, 'test_driver_id')
        self.assertIsInstance(result, ZmqDriverClient)

    def test_get_client_missing(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, {})

        with self.assertRaises(NotFound):
            get_client(consul_mock, 'test_driver_id')

    def test_get_host_and_port(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, json.loads(health_response))

        host_and_port = get_host_and_port(consul_mock, 'test_driver_id')
        self.assertEqual(host_and_port, (u'128.6.240.39', 42558))

    def test_get_host_and_port_missing(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, {})

        with self.assertRaises(NotFound):
            get_host_and_port(consul_mock, 'test_driver_id')

    def test_get_service_host_and_port(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, json.loads(health_response))

        host_and_port = get_service_host_and_port(consul_mock, 'instrument_driver', tag='test_driver_id')
        self.assertEqual(host_and_port, (u'128.6.240.39', 42558))

    def test_get_service_host_and_port_missing(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, {})

        response = get_service_host_and_port(consul_mock, 'instrument_driver', tag='test_driver_id')
        self.assertIsNone(response)

    def test_get_port_agent(self):
        self.maxDiff = None
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, json.loads(port_agent_response))

        pa_dict = get_port_agent(consul_mock, 'test_driver_id')
        self.assertEqual(pa_dict, {'command': {'host': u'128.6.240.39', 'port': 41347},
                                   'data': {'host': u'128.6.240.39', 'port': 41347},
                                   'sniff': {'host': u'128.6.240.39', 'port': 41347},
                                   'da': {'host': u'128.6.240.39', 'port': 41347}})

    def test_get_port_agent_missing(self):
        # mock the response from Consul
        consul_mock = mock.Mock()
        consul_mock.health.service.return_value = (1, {})

        with self.assertRaises(NotFound):
            get_port_agent(consul_mock, 'test_driver_id')

    # GET FROM REQUEST
    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_from_request_args(self, mocked):
        mocked.args = {'test': 5}
        mocked.form = {}
        mocked.json = {}
        val = get_from_request('test', 1)
        self.assertEqual(val, 5)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_from_request_form(self, mocked):
        mocked.args = {}
        mocked.form = {'test': 5}
        mocked.json = {}
        val = get_from_request('test', 1)
        self.assertEqual(val, 5)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_from_request_json(self, mocked):
        mocked.args = {}
        mocked.form = {}
        mocked.json = {'test': 5}
        val = get_from_request('test', 1)
        self.assertEqual(val, 5)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_from_request_default(self, mocked):
        mocked.args = {}
        mocked.form = {}
        mocked.json = {}
        val = get_from_request('test', 1)
        self.assertEqual(val, 1)

    # GET TIMEOUT
    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_timeout_args(self, mocked):
        mocked.args = {'timeout': 5}
        mocked.form = {}
        mocked.json = {}
        val = get_timeout()
        self.assertEqual(val, 5)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_timeout_form(self, mocked):
        mocked.args = {}
        mocked.form = {'timeout': 5}
        mocked.json = {}
        val = get_timeout()
        self.assertEqual(val, 5)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_timeout_json(self, mocked):
        mocked.args = {}
        mocked.form = {}
        mocked.json = {'timeout': 5}
        val = get_timeout()
        self.assertEqual(val, 5)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_timeout_default(self, mocked):
        mocked.args = {}
        mocked.form = {}
        mocked.json = {}
        val = get_timeout()
        self.assertEqual(val, 90000)

    @mock.patch('ooi_instrument_agent.utils.request')
    def test_get_timeout_invalid(self, mocked):
        mocked.args = {}
        mocked.form = {}
        mocked.json = {'timeout': 'bob'}
        val = get_timeout()
        self.assertEqual(val, 90000)
