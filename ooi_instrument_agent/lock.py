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
    """
    The LockManager class provides thread-safe locking/unlocking of instrument drivers via the Consul KV store

    Lock examples:

      <prefix>/master - master lock used to mediate access to the keystore
      <prefix>/RS10ENGC-XX00X-00-PARADA001 - Individual lock for a single driver

    When a lock is requested, LockManager will utilize the locking mechanisms present in Consul
     to obtain exclusive access to a master key (<prefix>/master) via the TimedRetryLock class. Once
     LockManager holds the master key it will create or delete, based on the requested action, the
     key at <prefix>/<driver_id>.
    """
    def __init__(self, consul):
        """
        :param consul: Instance of consulate.Consul
        """
        self.consul = consul
        self.prefix = 'lock'
        self.lock = TimedRetryLock.from_consul_object(consul, prefix=self.prefix)
        self.master_lock = '/'.join((self.prefix, 'master'))

    def check_lock(self, driver_id):
        """
        Check the current hold
        :param driver_id:
        :return: Current lock holder or None if the lock does not exist
        """
        return self._check_lock(self._get_lock_name(driver_id))

    def set_lock(self, driver_id, key):
        """
        Set the lock for driver_id to key. This action will fail if the lock is already held.
        :param driver_id: reference designator of driver to lock
        :param key: key representing the locking entity
        :return: holder of the lock at completion of this action
        """
        lock_name = self._get_lock_name(driver_id)
        with self.lock.acquire(self.master_lock):
            locker = self._check_lock(lock_name)
            if locker is None:
                self.consul.kv.set(lock_name, key)
                return key
            return locker

    def del_lock(self, driver_id):
        """
        Delete the lock for driver_id. This action is unconditional.
        :param driver_id: reference designator of driver to unlock
        :return: holder of the lock at completion of this action
        """
        lock_name = self._get_lock_name(driver_id)
        with self.lock.acquire(self.master_lock):
            locker = self._check_lock(lock_name)
            if locker is not None:
                self.consul.kv.delete(lock_name)
        return self._check_lock(lock_name)

    def get_locks(self):
        """
        Return all locks currently held under self.prefix
        :return: Dictionary of reference designator -> key entries
        """
        locks = self.consul.kv.find(self.prefix)
        return {key.split('/')[-1]: locks[key] for key in locks}

    def _get_lock_name(self, driver_id):
        """
        Given a driver_id, return the prefixed lock name
        :param driver_id: reference designator
        :return: prefixed lock name
        """
        return '/'.join((self.prefix, driver_id))

    def _check_lock(self, lock_name):
        """
        Return the current holder of a lock or None if not held
        :param lock_name: prefixed lock name
        :return: holder of the lock or None
        """
        return self.consul.kv.get(lock_name)


class TimedRetryLock(Lock):
    """
    This class overrides the consulate.Lock class to utilize a session with a TTL. Should
    the locking process not complete it's action within TTL*2 seconds, the session will
    expire and Consul will release the lock.
    """
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
        """
        Create a TimedRetryLock from an existing consulate.Consul object
        :param consul: consulate.Consul object
        :param ttl: TTL for the lock session
        :param num_retries: Maximum number of attempts to grab the lock before raising LockFailure
        :param prefix: KV prefix for this lock
        :return: instance of TimedRetryLock
        """
        session = consul._session
        base_uri = session._base_uri.replace('/session', '')
        return TimedRetryLock(base_uri, session._adapter, session,
                              session._dc, session._token, ttl, num_retries, prefix)

    @contextlib.contextmanager
    def acquire(self, key=None, value=None):
        """
        Acquire the specified key, optionally setting the corresponding value
        :param key: key to lock
        :param value: value to set
        :raises LockFailure
        """
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

    def _acquire(self, key=None, value=None):
        """
        Private method which actually acquires the lock
        :param key: key to lock
        :param value: value to set
        :raises LockFailure
        """
        self._session_id = self._session.create()
        self._item = '/'.join([self._prefix, (key or str(uuid.uuid4()))])
        response = self._put_response_body([self._item],
                                           {'acquire': self._session_id},
                                           value)
        if not response:
            self._session.destroy(self._session_id)
            raise LockFailure()
