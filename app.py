#!/usr/bin/env python3
# coding: utf-8

from tornado.websocket import WebSocketHandler
from tornado.web import Application
from tornado.ioloop import IOLoop
from tornado.options import parse_command_line

from datetime import datetime

class EchoWebSocket(WebSocketHandler):
    ping_data = ''
    ping_timer = None
    timeout_timer = None

    def reset_ping(self, schedule_ping = True):
        '''Remove ping and timeout timer and schedule new ping'''
        if self.ping_timer is not None:
            self.io_loop.remove_timeout(self.ping_timer)
        if self.timeout_timer is not None:
            self.io_loop.remove_timeout(self.timeout_timer)
        if schedule_ping:
            self.io_loop.call_later(30, self.send_ping)

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
        print("WebSocket opened")

    def on_message(self, message):
        '''Deal with messages'''
        self.reset_ping()
        self.write_message(message)

    def on_close(self):
        '''Deal with a closing connection'''
        self.reset_ping(False)
        print("WebSocket closed")


def main():
    parse_command_line()
    app = Application([(r'/', EchoWebSocket)])
    app.listen(8080)
    IOLoop.current().start()

if __name__ == '__main__':
    main()