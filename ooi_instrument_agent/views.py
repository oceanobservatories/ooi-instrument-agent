import json
import logging
import os
from functools import wraps

from consul import Consul
from flask import jsonify, request, Blueprint, send_file, safe_join, Response

from ooi_instrument_agent.lock import LockManager, Locked
from ooi_instrument_agent.utils import list_drivers, get_client, get_port_agent, get_from_request, get_timeout


page = Blueprint('instrument', __name__)
page.lock_manager = None
page.consul = None

log = logging.getLogger(__name__)


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
def handle_locked(error):
    response = jsonify(error.message)
    response.status_code = error.status_code
    return response


@page.before_app_first_request
def setup():
    page.consul = Consul()
    page.lock_manager = LockManager(page.consul)


@page.route('/api')
def get_drivers():
    return Response(json.dumps(list_drivers(page.consul)), mimetype='application/json')


@page.route('/api/<driver_id>')
def get_driver(driver_id):
    locker = page.lock_manager[driver_id]
    state = get_client(page.consul, driver_id).get_state()
    state['locked-by'] = locker
    return jsonify(state)


@page.route('/api/<driver_id>/portagent')
def get_driver_port_agent(driver_id):
    return jsonify(get_port_agent(page.consul, driver_id))


@page.route('/api/<driver_id>/ping')
def ping(driver_id):
    return jsonify(get_client(page.consul, driver_id).ping())


@page.route('/api/<driver_id>/discover', methods=['POST'])
@lockout
def discover(driver_id):
    return jsonify(get_client(page.consul, driver_id).discover(timeout=get_timeout()))


@page.route('/api/<driver_id>/set_init_params', methods=['POST'])
@lockout
def set_init_params(driver_id):
    config = get_from_request('config')
    return jsonify(get_client(page.consul, driver_id).set_init_params(config, timeout=get_timeout()))


@page.route('/api/<driver_id>/resource', methods=['GET'])
def get_resource(driver_id):
    resource = get_from_request('resource', 'DRIVER_PARAMETER_ALL')
    timeout = get_timeout()
    return jsonify(get_client(page.consul, driver_id).get_resource(resource, timeout=timeout))


@page.route('/api/<driver_id>/resource', methods=['POST'])
@lockout
def set_resource(driver_id):
    resource = get_from_request('resource')
    timeout = get_timeout()
    return jsonify(get_client(page.consul, driver_id).set_resource(resource, timeout=timeout))


@page.route('/api/<driver_id>/execute', methods=['POST'])
@lockout
def execute(driver_id):
    command = get_from_request('command')
    kwargs = get_from_request('kwargs', {})
    timeout = get_timeout()
    return jsonify(get_client(page.consul, driver_id).execute(command, timeout=timeout, **kwargs))


@page.route('/api/<driver_id>/shutdown', methods=['POST'])
@lockout
def shutdown(driver_id):
    return jsonify(get_client(page.consul, driver_id).shutdown())


@page.route('/api/<driver_id>/set_log_level', methods=['POST'])
@lockout
def set_log_level(driver_id):
    level = get_from_request('level')
    timeout = get_timeout()
    return jsonify(get_client(page.consul, driver_id).set_log_level(timeout=timeout, level=level))


@page.route('/api/<driver_id>/lock', methods=['GET'])
def get_lock(driver_id):
    return jsonify({'locked-by': page.lock_manager[driver_id]})


@page.route('/api/<driver_id>/lock', methods=['POST'])
def set_lock(driver_id):
    key = request.form.get('key')
    page.lock_manager[driver_id] = key
    return jsonify({'locked-by': page.lock_manager[driver_id]})


@page.route('/api/<driver_id>/unlock', methods=['POST'])
@page.route('/api/<driver_id>/lock', methods=['DELETE'])
def unlock(driver_id):
    del page.lock_manager[driver_id]
    return jsonify({'locked-by': page.lock_manager[driver_id]})


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
