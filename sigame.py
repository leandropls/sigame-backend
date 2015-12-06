# coding: utf-8

from inspect import getargspec
import re
import json

class NameCollisionError(Exception):
    pass

class Connection(object):
    _name_regexp = re.compile(r'^[\w ]{1,32}$')
    name = None
    realname = None

    def __init__(self, channel, upstream):
        self.upstream = upstream
        self.channel = channel
        self.srvname = channel.srvname

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
        if self.name is not None:
            self.channel.remove_name(self.name)
        self.channel = None
        self.upstream = None

    ## Server initiated actions
    def srv_message(self, message):
        self.upstream.send(message)

    ## User initiated actions
    def usr_echo(self, message):
        '''Process echo command'''
        if not isinstance(message, str):
            return
        self.srv_message(json.dumps([self.srvname, 'ECHO', message]))

    def usr_register(self, name):
        '''Process REGISTER command'''
        # Don't register registered users
        if self.name is not None:
            return

        # Reject invalid names
        if not isinstance(name, str) or self._name_regexp.match(name) is None:
            return

        # Register user
        realname = name
        name = name.lower()
        try:
            self.channel.add_name(name, self)
        except NameCollisionError:
            self.srv_message(json.dumps(
                [self.srvname, 'ERROR', 433, 'Name already in use.']))
            return
        self.realname = realname
        self.name = name
        self.channel.srv_message(json.dumps([self.srvname, 'REGISTER', self.realname]))

    def usr_location(self, lat, lng):
        '''Process LOCATION command'''
        if self.realname is None:
            return
        if not (isinstance(lat, (int, float)) and
                isinstance(lng, (int, float))):
            return
        self.channel.srv_message(json.dumps([self.realname, 'LOCATION', lat, lng]))

class Channel(object):
    def __init__(self, channame, sigame):
        self.names = {}
        self.channame = channame
        self.sigame = sigame
        self.srvname = sigame.name

    def __len__(self):
        return len(self.users)

    def connection(self, upstream):
        '''Add and return new connection to channel'''
        conn = Connection(self, upstream)
        return conn

    def add_name(self, name, conn):
        '''Add name to channel'''
        if name in self.names:
            raise NameCollisionError
        self.names[name] = conn

    def remove_name(self, name):
        '''Remove name from channel'''
        try:
            del self.names[name]
        except KeyError:
            return

    def srv_message(self, *message):
        '''Send message to all users'''
        for conn in self.names.values():
            conn.srv_message(*message)

class Sigame(object):
    _channel_regexp = re.compile(r'^[\w]{1,64}$')

    def __init__(self, servername):
        self.name = servername
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
