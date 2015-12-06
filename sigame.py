# coding: utf-8

from inspect import getargspec
import re
import json

class Connection(object):
    def __init__(self, channel, upstream):
        self.upstream = upstream
        self.channel = channel

    ## Connection interface
    def message(self, message):
        '''Parse message and take appropriate action'''
        # Parse
        try:
            message = json.loads(message)
        except:
            return
        if not isinstance(message, list) or len(message) < 1:
            return
        if not isinstance(message[0], str):
            return
        if not all((isinstance(x, (str, int, float)) for x in message[1:])):
            return

        # Find method
        try:
            method = getattr(self, 'usr_%s' % message[0].lower())
        except AttributeError:
            return
        margs = getargspec(method)
        argcheck = len(message) >= len(margs.args) # count self and command
        argcheck &= margs.varargs is not None or len(message) == len(margs.args)
        if not argcheck:
            return

        # Call method
        method(*message[1:])

    def close(self):
        '''Close connection'''
        self.channel.remove_connection(self)
        self.channel = None
        self.upstream = None

    ## Server initiated actions
    def srv_message(self, *message):
        self.upstream.send(json.dumps(message))

    ## User initiated actions
    def usr_echo(self, message):
        '''Process echo command'''
        if not isinstance(message, str):
            return
        self.srv_message('ECHO', message)

class Channel(object):
    def __init__(self, channame, sigame):
        self.connections = set()
        self.channame = channame
        self.sigame = sigame

    def __len__(self):
        return len(self.users)


    def connection(self, upstream):
        '''Add and return new connection to channel'''
        conn = Connection(self, upstream)
        self.connections.add(conn)
        return conn

    def remove_connection(self, conn):
        '''Remove connection from channel'''
        try:
            self.connections.remove(conn)
        except KeyError:
            return

class Sigame(object):
    _channel_regexp = re.compile(r'^[\w]{1,64}')

    def __init__(self):
        self.channels = {}

    def _get_channel(self, channame):
        '''Get channel'''
        if self._channel_regexp.match(channame) is None:
            raise KeyError

        if channame in self.channels:
            return self.channels[channame]

        channel = Channel(channame, self)
        self.channels[channame] = channel
        return channel

    def connection(self, channame, upstream):
        '''Create and return new connection to the specified channel'''
        if not isinstance(channame, str):
            raise KeyError
        channame = channame.lower()
        channel = self._get_channel(channame)
        return channel.connection(upstream)
