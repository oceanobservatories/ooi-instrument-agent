#!/usr/bin/env python
import datetime
import json
import logging
from collections import deque

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.endpoints import UNIXServerEndpoint
from twisted.internet.protocol import Factory, Protocol, connectionDone, ClientCreator
from twisted.python import log
from twisted.web.client import Agent, HTTPConnectionPool, readBody

from ooi_instrument_agent.common import get_sniffer_socket


class ConsulConnectionPool(HTTPConnectionPool):
    maxPersistentPerHost = 6
    cachedConnectionTimeout = 600


pool = ConsulConnectionPool(reactor)
agent = Agent(reactor, pool=pool)


class RequestProtocol(Protocol):
    """
    Handle incoming requests for sniffer data
    """

    def dataReceived(self, data):
        """
        Called asynchronously when data is received from this connection
        Expects a JSON-encoded, 2 element list [reference_designator, user_key]

        Any other input will be ignored
        """
        request = json.loads(data)
        if len(request) == 2:
            refdes, user_key = request
            deferred_protocol = self.factory.get_sniffer(refdes, user_key)
            deferred_protocol.addCallback(self.got_sniffer_protocol, refdes=refdes, user_key=user_key)

    def got_sniffer_protocol(self, protocol, refdes=None, user_key=None):
        """
        If a valid sniffer protocol is found, ask it for the data currently in the queue
        and return it to the requester. Otherwise, return a connection failed response.
        """
        if protocol is not None:
            data = protocol.get_data()
        else:
            data = 'FAILED TO CONNECT (%r, %r)\n' % (refdes, user_key)

        self.transport.write(data)
        self.transport.loseConnection()


class RequestFactory(Factory):
    """
    Factory to handle creating a request protocol
    Maintains the dictionary of active sniffer protocols and includes helper methods for fetching/creating them.
    """
    protocol = RequestProtocol

    def __init__(self):
        self.sniff_protocols = {}
        self.client_creator = ClientCreator(reactor, SniffProtocol)

    @inlineCallbacks
    def get_sniffer(self, refdes, user_key):
        """
        Return the sniffer protocol object for the specified reference designator and user key.
        If this protocol object does not currently exist, create it.
        If we fail to connect for any reason, returns None
        """
        key = hash((refdes, user_key))
        if key not in self.sniff_protocols:
            # prevent entering this code when we yield control
            # to make our sniffer connection
            self.sniff_protocols[key] = None
            host, port = yield self.locate(refdes)
            if host is None or port is None:
                # no such port agent found
                # cleanup after ourselves, then raise an Exception
                del self.sniff_protocols[key]
                log.msg('Unable to create sniffer session for %r %r, NOT FOUND' % (refdes, user_key))
                returnValue(None)

            log.msg('Creating sniffer session for %r %r' % (refdes, user_key))
            try:
                protocol = yield self.client_creator.connectTCP(host, port, timeout=10)
                protocol.refdes = refdes
                protocol.key = user_key
                protocol.lost_connection_callback = self.sniffer_closed(key)
                self.sniff_protocols[key] = protocol
            except Exception as e:
                # unable to connect
                # cleanup after ourselves, then re-raise the original Exception
                del self.sniff_protocols[key]
                log.msg('Unable to create sniffer session for %r %r, Exception: %s' % (refdes, user_key, e))
                returnValue(None)

        protocol = self.sniff_protocols.get(key)
        returnValue(protocol)

    @inlineCallbacks
    def locate(self, refdes):
        """
        Query Consul for the IP address and port number of the input reference designator
        """
        url = 'http://localhost:8500/v1/health/service/sniff-port-agent?tag=%s&passing=true' % str(refdes)
        log.msg(url)
        response = yield agent.request('GET', url)
        svc = yield readBody(response)
        svc = json.loads(svc)
        if len(svc) == 1:
            svc = svc[0]
            addr = svc['Node']['Address']
            port = svc['Service']['Port']
            returnValue((addr, port))

        returnValue((None, None))

    def sniffer_closed(self, key):
        """
        Closure which will allow the specified sniffer protocol to clean itself up from the dictionary
        when disconnected.
        """
        def inner(ignore):
            del self.sniff_protocols[key]
        return inner


class SniffProtocol(Protocol):
    """
    Protocol object to buffer the data received from the target port agent.
    Internally, this data is stored in a deque. If the maxlen is exceeded, the oldest data will be dropped.
    """
    def __init__(self, maxlen=1000):
        self.buffer = deque(maxlen=maxlen)
        self.refdes = None
        self.key = None
        self.timestamp = None
        self.lost_connection_callback = None

    def get_data(self):
        """
        Return the current contents of the internal buffer and update the timestamp.
        """
        self.timestamp = datetime.datetime.utcnow()
        return_list = []
        for i in xrange(len(self.buffer)):
            return_list.append(self.buffer.popleft())
        return ''.join(return_list)

    def dataReceived(self, data):
        """
        Called asynchronously when data is received from this connection.
        Append the received data to the internal buffer.
        Compare the current time to the last time the buffer was read,
        if this exceeds our maximum time, drop the connection.
        """
        self.buffer.append(data)
        now = datetime.datetime.utcnow()
        if self.timestamp is None:
            self.timestamp = now

        if now - self.timestamp > datetime.timedelta(minutes=1):
            self.transport.loseConnection()

    def connectionLost(self, reason=connectionDone):
        log.msg('Disconnected from sniffer port for %r %r' % (self.refdes, self.key))
        if callable(self.lost_connection_callback):
            self.lost_connection_callback(self)


class SnifferGateway(object):
    def __init__(self, sock_name):
        self.server = UNIXServerEndpoint(reactor, sock_name)
        self.server.listen(RequestFactory())


def configure_logging():
    log_format = '%(asctime)-15s %(levelname)s %(message)s'
    logging.basicConfig(format=log_format)
    logger = logging.getLogger('port_agent')
    logger.setLevel(logging.INFO)
    observer = log.PythonLoggingObserver('port_agent')
    observer.start()


if __name__ == '__main__':
    configure_logging()
    sockfile = get_sniffer_socket()
    sg = SnifferGateway(sockfile)
    exit(reactor.run())
