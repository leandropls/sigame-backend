# coding: utf-8

from inspect import getargspec
import re, json, os, hashlib
Inf = float('Inf')

class NameCollisionError(Exception):
    pass

class Connection(object):
    _name_regexp = re.compile(r'^[\w ]{1,32}$')
    name = None
    realname = None
    active = True

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
        min_args = len(margs.args) - (len(margs.defaults) if margs.defaults is not None else 0)
        max_args = len(margs.args) if margs.varargs is None else Inf
        if not (min_args <= len(message) <= max_args):
            return

        # Call method
        method(*message[1:])

    def close(self):
        '''Close connection'''
        if not self.active:
            return
        self.active = False
        if self.name is not None:
            self.channel.srv_message(json.dumps([self.realname, 'QUIT']))
            self.channel.remove_name(self.name, self)
        self.upstream.close()
        self.channel = None
        self.upstream = None

    ## Server initiated actions
    def srv_message(self, message):
        '''Send message to user'''
        self.upstream.send(message)

    def srv_register(self, realname, oldtoken):
        '''Register user'''
        if not self.active:
            return
        name = realname.lower()
        token = hashlib.sha1(os.urandom(8)).hexdigest()
        try:
            self.channel.add_name(name, self, token, oldtoken)
        except NameCollisionError:
            self.srv_message(json.dumps(
                [self.srvname, 'ERROR', 433, 'Name already in use.']))
            return
        self.realname = realname
        self.name = name
        self.channel.srv_message(
            json.dumps([self.srvname, 'REGISTER', self.realname]), self)
        self.srv_message(
            json.dumps([self.srvname, 'REGISTER', self.realname, token]))
        self.channel.srv_users(self)

    ## User initiated actions
    def usr_echo(self, message):
        '''Process ECHO command'''
        if not isinstance(message, str):
            return
        self.srv_message(json.dumps([self.srvname, 'ECHO', message]))

    def usr_register(self, name, token = None):
        '''Process REGISTER command'''
        # Don't register registered users
        if self.name is not None:
            return

        # Reject invalid names
        if not isinstance(name, str) or self._name_regexp.match(name) is None:
            return

        # Register user
        self.srv_register(name, token)

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

    def add_name(self, name, conn, token, oldtoken):
        '''Add name to channel'''
        if name in self.names: # Name already taken
            exstconn, exsttoken = self.names[name]
            if exsttoken != oldtoken: # Token is wrong
                raise NameCollisionError
            exstconn.close() # Kill old connection
        self.names[name] = (conn, token) # Register connection

    def remove_name(self, name, conn = None):
        '''Remove name from channel'''
        if name not in self.names:
            return
        if conn is not None and self.names[name][0] != conn:
            return
        del self.names[name]

    def srv_message(self, message, except_conn = None):
        '''Send message to all users'''
        if except_conn is None:
            for conn, token in self.names.values():
                conn.srv_message(message)
        else:
            for conn, token in self.names.values():
                if conn is except_conn:
                    continue
                conn.srv_message(message)

    def srv_users(self, conn):
        '''Send list of names to the specified connection'''
        msg = [self.srvname, 'USERS']
        msg.extend((conn.realname for conn, token in self.names.values()))
        conn.srv_message(json.dumps(msg))


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
