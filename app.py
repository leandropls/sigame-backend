#!/usr/bin/env python3
# coding: utf-8

from sigame import Sigame

from tornado.websocket import WebSocketHandler
from tornado.web import Application
from tornado.ioloop import IOLoop
from tornado.options import parse_command_line

from datetime import datetime
import json

sigame = Sigame()

class SigameUpstream(object):
    def __init__(self, wsh):
        self.wsh = wsh

    def send(self, message):
        assert isinstance(message, str)
        self.wsh.write_message(message)

    def close(self):
        self.wsh.close()

class SigameWebSocket(WebSocketHandler):
    ping_data = ''
    ping_timer = None
    timeout_timer = None
    channame = None
    conn = None

    def get(self, channame, *args, **kwargs):
        self.channame = channame
        return super().get(*args, **kwargs)

    def reset_ping(self, schedule_ping = True):
        '''Remove ping and timeout timer and schedule new ping'''
        if self.ping_timer is not None:
            self.io_loop.remove_timeout(self.ping_timer)
            self.ping_timer = None
        if self.timeout_timer is not None:
            self.io_loop.remove_timeout(self.timeout_timer)
            self.timeout_timer = None
        if schedule_ping:
            self.ping_timer = self.io_loop.call_later(30, self.send_ping)

    def send_ping(self):
        '''Send ping and schedules timeout'''
        ping_data = datetime.now().strftime('%s').encode('ascii')
        self.ping_data = ping_data
        self.ping(ping_data)
        self.timeout_timer = self.io_loop.call_later(30, self.on_timeout)

    def on_pong(self, data):
        '''Deal with pongs'''
        if data != self.ping_data:
            return
        self.reset_ping()

    def on_timeout(self):
        '''Close connection for timeout'''
        self.reset_ping(False)
        self.close(1006, 'Ping timeout')

    def check_origin(self, origin):
        '''Accept all origins'''
        return True

    def open(self):
        '''Deal with a new connection'''
        self.io_loop = IOLoop.current()
        self.reset_ping()
        upstream = SigameUpstream(self)
        self.conn = sigame.connection(self.channame, upstream)

    def on_message(self, message):
        '''Deal with messages'''
        self.reset_ping()
        self.conn.message(message)

    def on_close(self):
        '''Deal with a closing connection'''
        self.reset_ping(False)
        self.conn.close()


def main():
    parse_command_line()
    app = Application([(r'/(\w{1,64})', SigameWebSocket)])
    app.listen(8080)
    IOLoop.current().start()

if __name__ == '__main__':
    main()