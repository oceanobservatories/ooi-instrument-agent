import json
import logging

from flask import request
from werkzeug.exceptions import abort

from ooi_instrument_agent.client import ZmqDriverClient


DEFAULT_TIMEOUT = 90000
log = logging.getLogger(__name__)


def get_client(consul, driver_id):
    """
    Create a ZmqDriverClient for the specified driver_id
    :param consul: Instance of consulate.Consul
    :param driver_id: Reference designator of target driver
    :return: ZmqDriverClient if found, otherwise 404
    """
    return ZmqDriverClient(*get_host_and_port(consul, driver_id))


def get_host_and_port(consul, driver_id):
    """
    Return the host and port for the specified driver_id
    :param consul: Instance of consulate.Consul
    :param driver_id: Reference designator of target driver
    :return: host, port if found, otherwise 404
    """
    host_and_port = get_service_host_and_port(consul, 'instrument_driver', tag=driver_id)
    if host_and_port is None:
        abort(404)
    return host_and_port


def get_service_host_and_port(consul, service_id, tag=None):
    """
    Return the first passing host and port for the specified service_id
    :param consul: Instance of consulate.Consul
    :param service_id: service_id
    :param tag: tag
    :return: host, port if found, otherwise None
    """
    matches = consul.health.service(service_id, tag=tag, passing=True)
    for match in matches:
        host = match.get('Node', {}).get('Address')
        port = match.get('Service', {}).get('Port')
        if host and port:
            return host, port


def list_drivers(consul):
    """
    Return a list of all passing drivers currently registered in Consul
    :param consul: Instance of consulate.Consul
    :return: List of reference designators
    """
    drivers = []
    passing = consul.health.service('instrument_driver', passing=True)
    for each in passing:
        tags = each.get('Service', {}).get('Tags', [])
        drivers.extend(tags)
    return drivers


def get_port_agent(consul, driver_id):
    """
    Fetch the port agent information for the specified driver from Consul
    :param consul: Instance of consulate.Consul
    :param driver_id: Reference designator of target driver
    :return: Dictionary containing the port agent data for the specified driver
    """
    return_dict = {}
    for name, service_id in [('data', 'port-agent'),
                             ('command', 'command-port-agent'),
                             ('sniff', 'sniff-port-agent'),
                             ('da', 'da-port-agent')]:
        host_and_port = get_service_host_and_port(consul, service_id, tag=driver_id)
        if host_and_port:
            host, port = host_and_port
            return_dict[name] = {'host': host, 'port': port}
    return return_dict


def get_from_request(name, default=None):
    """
    Extract the target parameter from a Flask request object. Attempts to do the right
    thing whether the input data was passed as URL query params, a form or as JSON.
    :param name: Target parameter
    :param default: Default value to return if not found
    :return: Extracted value if found, else default
    """

    def extract(value_dict, name):
        val = value_dict.get(name)
        if val is None:
            return default
        try:
            val = json.loads(val)
        except (TypeError, ValueError):
            pass
        return val

    if request.args:
        return extract(request.args, name)
    if request.form:
        return extract(request.form, name)

    if request.json:
        return request.json.get(name, default)

    return default


def get_timeout():
    """
    Get the timeout from the request object as an int
    :return: timeout
    """
    val = get_from_request('timeout')

    try:
        return int(val)
    except TypeError:
        return DEFAULT_TIMEOUT
