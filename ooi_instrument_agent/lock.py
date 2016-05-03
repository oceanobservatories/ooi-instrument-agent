from collections import MutableMapping
from logging import getLogger

log = getLogger(__name__)


class Locked(Exception):
    status_code = 409

    def __init__(self, message, status_code=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class LockManager(MutableMapping):
    def __init__(self, consul, prefix='agent/lock'):
        self.consul = consul
        self.prefix = prefix

    def __getitem__(self, key):
        key = '/'.join((self.prefix, key))
        return self._get_value(key)

    def __setitem__(self, key, value):
        key = '/'.join((self.prefix, key))
        current = self._get(key)
        if current is not None:
            value = current.get('Value')
            if value is not None:
                raise Locked({'locked-by': value})
            modify_index = current.get('ModifyIndex')
        else:
            modify_index = 0

        success = self.consul.kv.put(key, value, cas=modify_index)
        if success:
            return key
        else:
            return self[key]

    def __delitem__(self, key):
        key = '/'.join((self.prefix, key))
        current = self._get(key)
        if current is not None:
            modify_index = current.get('ModifyIndex')
            self.consul.kv.delete(key, cas=modify_index)

    def __len__(self):
        index, values = self.consul.kv.get(self.prefix, recurse=True)
        if values is None:
            return 0
        return len(values) - 1

    def __iter__(self):
        index, values = self.consul.kv.get(self.prefix, recurse=True)
        if values is not None:
            for value in values:
                yield value.get('Key').replace(self.prefix, '').lstrip('/')

    def _get(self, item):
        index, value = self.consul.kv.get(item)
        return value

    def _get_value(self, item):
        value = self._get(item)
        if value is None:
            return value
        return value.get('Value')
