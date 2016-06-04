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

    def dataReceived(self, data):
        """
        Called asynchronously when data is received from this connection
        """
        request = json.loads(data)
        if len(request) == 2:
            refdes, user_key = request
            deferred_protocol = self.factory.get_sniffer(refdes, user_key)
            deferred_protocol.addCallback(self.got_sniffer_protocol)

    def got_sniffer_protocol(self, protocol):
        if protocol is not None:
            data = protocol.get_data()
            log.msg('data: %r' % data)
            self.transport.write(data)

        self.transport.loseConnection()

    def connectionMade(self):
        log.msg('New request connection received')

    def connectionLost(self, reason=connectionDone):
        log.msg('request complete')


class RequestFactory(Factory):
    protocol = RequestProtocol

    def __init__(self):
        self.sniff_protocols = {}
        self.client_creator = ClientCreator(reactor, SniffProtocol)

    @inlineCallbacks
    def get_sniffer(self, refdes, user_key):
        key = refdes + user_key
        if key not in self.sniff_protocols:
            self.sniff_protocols[key] = None
            host, port = yield self.locate(refdes)
            if host is None or port is None:
                raise Exception
            protocol = yield self.client_creator.connectTCP(host, port, timeout=10)
            protocol.refdes = refdes
            protocol.lost_connection_callback = self.sniffer_closed(key)
            self.sniff_protocols[key] = protocol
        protocol = self.sniff_protocols.get(key)
        if protocol is None:
            raise Exception
        returnValue(protocol)

    @inlineCallbacks
    def locate(self, refdes):
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
        def inner(ignore):
            del self.sniff_protocols[key]
        return inner


class SniffProtocol(Protocol):
    def __init__(self, maxlen=1000):
        self.buffer = deque(maxlen=maxlen)
        self.refdes = None
        self.timestamp = None
        self.lost_connection_callback = None

    def get_data(self):
        log.msg("sniffer get_data")
        self.timestamp = datetime.datetime.utcnow()
        return_list = []
        for i in xrange(len(self.buffer)):
            return_list.append(self.buffer.popleft())
        return ''.join(return_list)

    def dataReceived(self, data):
        """
        Called asynchronously when data is received from this connection
        """
        log.msg("sniffer got data: %r" % data)
        self.buffer.append(data)
        now = datetime.datetime.utcnow()
        if self.timestamp is None:
            self.timestamp = now

        if now - self.timestamp > datetime.timedelta(minutes=1):
            self.transport.loseConnection()

    def connectionMade(self):
        log.msg('Connected to sniffer port for %s' % self.refdes)

    def connectionLost(self, reason=connectionDone):
        log.msg('Disconnected from sniffer port for %s (%s)' % (self.refdes, reason))
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