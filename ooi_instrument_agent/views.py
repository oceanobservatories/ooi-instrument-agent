import json
import logging
import os
import socket
import gevent
import requests
from functools import wraps

from consul import Consul
from flask import jsonify, request, Blueprint, send_file, safe_join, Response

from ooi_instrument_agent.client import TimeoutException, ParameterException
from ooi_instrument_agent.common import get_sniffer_socket, stopwatch
from ooi_instrument_agent.lock import LockManager, Locked
from ooi_instrument_agent.utils import list_drivers, get_client, get_port_agent, get_from_request, get_timeout


page = Blueprint('instrument', __name__)
page.lock_manager = None
page.consul = None

log = logging.getLogger(__name__)
sniff_sockfile = get_sniffer_socket()


def lockout(func):
    """
    Decorator which requires that the target instrument be unlocked or the supplied key matches the lock holder
    """
    @wraps(func)
    def inner(driver_id):
        key = get_from_request('key')
        locker = page.lock_manager[driver_id]
        if locker is None or locker == key:
            return func(driver_id)
        raise Locked({'locked-by': locker})
    return inner


@page.before_request
def before_request():
    log.info('Request: %r', request.url)


@page.errorhandler(Locked)
@page.errorhandler(TimeoutException)
@page.errorhandler(ParameterException)
def handle_locked(error):
    response = jsonify(error.message)
    response.status_code = error.status_code
    return response


@page.before_app_first_request
def setup():
    page.consul = Consul()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    page.consul.http.session.mount('http://', adapter)
    page.lock_manager = LockManager(page.consul)


@page.route('/api')
def get_drivers():
    running_drivers = list_drivers(page.consul)
    return Response(json.dumps(running_drivers), mimetype='application/json')


@page.route('/api/status')
def get_drivers_status():
    startswith = get_from_request('startswith')
    contains = get_from_request('contains')
    running_drivers = list_drivers(page.consul)

    if startswith:
        drivers = [x for x in running_drivers if x.startswith(startswith)]
    elif contains:
        drivers = [x for x in running_drivers if contains in x]
    else:
        drivers = running_drivers

    # fetch all
    greenlets = []
    for driver_id in drivers:
        greenlets.append((driver_id, gevent.spawn(get_driver_resource_state, driver_id)))

    # resolve results
    result = {}
    for each in greenlets:
        driver_id, greenlet = each
        status = greenlet.get()
        result[driver_id] = status

    return Response(json.dumps(result), mimetype='application/json')


@stopwatch(log)
@page.route('/api/<driver_id>')
def get_driver(driver_id):
    return jsonify(get_driver_overall_state(driver_id))


def get_driver_overall_state(driver_id):
    locker = page.lock_manager[driver_id]
    with get_client(page.consul, driver_id) as client:
        state = client.get_state()
        state['locked-by'] = locker
        return state


def get_driver_resource_state(driver_id):
    with get_client(page.consul, driver_id) as client:
        state = client.get_resource_state().get('value')
        return state


@page.route('/api/<driver_id>/portagent')
def get_driver_port_agent(driver_id):
    return jsonify(get_port_agent(page.consul, driver_id))


@page.route('/api/<driver_id>/ping')
def ping(driver_id):
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.ping())


@page.route('/api/<driver_id>/state')
def resource_state(driver_id):
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.get_resource_state())


@page.route('/api/<driver_id>/discover', methods=['POST'])
@lockout
def discover(driver_id):
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.discover(timeout=get_timeout()))


@page.route('/api/<driver_id>/set_init_params', methods=['POST'])
@lockout
def set_init_params(driver_id):
    config = get_from_request('config')
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.set_init_params(config, timeout=get_timeout()))


@page.route('/api/<driver_id>/resource', methods=['GET'])
def get_resource(driver_id):
    resource = get_from_request('resource', 'DRIVER_PARAMETER_ALL')
    timeout = get_timeout()
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.get_resource(resource, timeout=timeout))


@page.route('/api/<driver_id>/resource', methods=['POST'])
@lockout
def set_resource(driver_id):
    resource = get_from_request('resource')
    timeout = get_timeout()
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.set_resource(resource, timeout=timeout))


@page.route('/api/<driver_id>/execute', methods=['POST'])
@lockout
def execute(driver_id):
    command = get_from_request('command')
    kwargs = get_from_request('kwargs', {})
    # timeout =re get_timeout()
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.execute(command, **kwargs))


@page.route('/api/<driver_id>/shutdown', methods=['POST'])
@lockout
def shutdown(driver_id):
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.shutdown())


@page.route('/api/<driver_id>/set_log_level', methods=['POST'])
@lockout
def set_log_level(driver_id):
    level = get_from_request('level')
    timeout = get_timeout()
    with get_client(page.consul, driver_id) as client:
        return jsonify(client.set_log_level(timeout=timeout, level=level))


@page.route('/api/<driver_id>/lock', methods=['GET'])
def get_lock(driver_id):
    return jsonify({'locked-by': page.lock_manager[driver_id]})


@page.route('/api/<driver_id>/lock', methods=['POST'])
def set_lock(driver_id):
    key = get_from_request('key')
    page.lock_manager[driver_id] = key
    return jsonify({'locked-by': page.lock_manager[driver_id]})


@page.route('/api/<driver_id>/unlock', methods=['POST'])
@page.route('/api/<driver_id>/lock', methods=['DELETE'])
def unlock(driver_id):
    del page.lock_manager[driver_id]
    return jsonify({'locked-by': page.lock_manager[driver_id]})


@page.route('/api/<driver_id>/sniff')
def sniff(driver_id):
    key = get_from_request('key')
    command = json.dumps([driver_id, key])
    data = get_sniff_data(command)
    return data


@page.route('/api/locks')
def locks():
    return jsonify({'locks': dict(page.lock_manager.iteritems())})


@page.route('/app')
def app():
    source_dir = 'agent-web/app'
    return send_file(os.path.join(source_dir, 'index.html'))


@page.route('/css/<cssfile>')
def css(cssfile):
    source_dir = 'agent-web/app/css'
    return send_file(safe_join(source_dir, cssfile))


@page.route('/js/<jsfile>')
def js(jsfile):
    source_dir = 'agent-web/app/js'
    return send_file(safe_join(source_dir, jsfile))


@page.route('/partials/<pfile>')
def partials(pfile):
    source_dir = 'agent-web/app/partials'
    return send_file(safe_join(source_dir, pfile))


def get_sniff_data(command):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect(sniff_sockfile)
    sock.send(command)
    data = ''
    while True:
        chunk = sock.recv(4096)
        if chunk:
            data += chunk
        else:
            break

    sock.close()
    return data
