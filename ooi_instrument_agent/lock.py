import contextlib
import time
import uuid
from logging import getLogger

from consulate import LockFailure
from consulate.api import Lock

NUM_LOCK_RETRIES = 3

log = getLogger(__name__)


class Locked(Exception):
    status_code = 409

    def __init__(self, message, status_code=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class LockManager(object):
    def __init__(self, consul):
        self.consul = consul
        self.prefix = 'lock'
        self.lock = TimedRetryLock.from_consul_object(consul, prefix=self.prefix)
        self.master_lock = '/'.join((self.prefix, 'master'))

    def check_lock(self, driver_id):
        return self._check_lock(self._get_lock_name(driver_id))

    def set_lock(self, driver_id, key):
        lock_name = self._get_lock_name(driver_id)
        with self.lock.acquire(self.master_lock):
            locker = self._check_lock(lock_name)
            if locker is None:
                self.consul.kv.set(lock_name, key)
                return key
            return locker

    def del_lock(self, driver_id):
        lock_name = self._get_lock_name(driver_id)
        with self.lock.acquire(self.master_lock):
            locker = self._check_lock(lock_name)
            if locker is not None:
                self.consul.kv.delete(lock_name)
        return self._check_lock(lock_name)

    def get_locks(self):
        locks = self.consul.kv.find(self.prefix)
        return {key.split('/')[-1]: locks[key] for key in locks}

    def _get_lock_name(self, driver_id):
        return '/'.join((self.prefix, driver_id))

    def _check_lock(self, lock_name):
        return self.consul.kv.get(lock_name)


class TimedRetryLock(Lock):
    DEFAULT_TTL = '10s'
    DEFAULT_RETRIES = 3

    def __init__(self, uri, adapter, session, datacenter=None, token=None, ttl=None, num_retries=None, prefix=None):
        """Consul Lock with a TTL-constrained session
        Will retry num_retries to acquire the lock before raising LockFailure
        :param str ttl: Session TTL
        :param int num_retries: Number of attempts to acquire the lock
        """
        super(TimedRetryLock, self).__init__(uri, adapter, session, datacenter, token)
        self.ttl = ttl if ttl is not None else self.DEFAULT_TTL
        self.num_retries = num_retries if num_retries is not None else self.DEFAULT_RETRIES
        self._prefix = prefix if prefix is not None else self.DEFAULT_PREFIX

    # noinspection PyProtectedMember
    @staticmethod
    def from_consul_object(consul, ttl=None, num_retries=None, prefix=None):
        session = consul._session
        base_uri = session._base_uri.replace('/session', '')
        return TimedRetryLock(base_uri, session._adapter, session,
                              session._dc, session._token, ttl, num_retries, prefix)

    @contextlib.contextmanager
    def acquire(self, key=None, value=None):
        tries = 0
        while True:
            try:
                self._acquire(key, value)
                yield
                self._release()
                return
            except LockFailure:
                if tries >= self.num_retries:
                    raise
                tries += 1
                time.sleep(.1)

    def _acquire2(self, key=None, value=None):
        self._session_id = self._session.create()
        self._item = '/'.join([self._prefix, (key or str(uuid.uuid4()))])
        log.debug('Acquiring a lock of %s for session %s', self._item, self._session_id)
        response = self._put_response_body([self._item], {'acquire': self._session_id}, value)
        if not response:
            self._session.destroy(self._session_id)
            raise LockFailure()

    def _acquire(self, key=None, value=None):
        self._session_id = self._session.create()
        self._item = '/'.join([self._prefix, (key or str(uuid.uuid4()))])
        response = self._put_response_body([self._item],
                                           {'acquire': self._session_id},
                                           value)
        if not response:
            self._session.destroy(self._session_id)
            raise LockFailure()
