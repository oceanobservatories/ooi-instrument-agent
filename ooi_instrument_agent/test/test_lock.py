import unittest

import consul

from ooi_instrument_agent.lock import LockManager, Locked


prefix = 'unittest/locks'

test_locks = {
    'driver_one': 'one',
    'driver_two': 'two'
}


# These unit tests require a running Consul instance
class LockTest(unittest.TestCase):
    def setUp(self):
        self.consul = consul.Consul()
        self.consul.kv.delete(prefix, recurse=True)

    def test_iter(self):
        lm = LockManager(self.consul, prefix=prefix)
        lm.update(test_locks)
        self.assertDictEqual(dict(lm.iteritems()), test_locks)

    def test_lock(self):
        lm = LockManager(self.consul, prefix=prefix)
        lock_id = 'lock_me'
        locker = 'test'
        lm[lock_id] = locker

        # locking again with the same id should raise Locked
        with self.assertRaises(Locked):
            lm[lock_id] = locker

        # attempt to lock with a different ID
        with self.assertRaises(Locked):
            lm[lock_id] = 'fail'

        # remove the lock
        del lm[lock_id]

    def test_locks_len(self):
        lm = LockManager(self.consul, prefix=prefix)
        # no locks
        self.assertEqual(len(lm), 0)
        # create 2 locks
        lm.update(test_locks)
        self.assertEqual(len(lm), 2)
