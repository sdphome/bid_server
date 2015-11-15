#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Rule Of Optimization: Prototype before polishing. Get it
#                       working before you optimize it.
import select, socket, os, threading, sys, signal, stat
import time, struct, re, traceback

from collections import defaultdict

host = '127.0.0.1'
port = 8098
timeout = 15
DOCUMENT_ROOT = os.getcwd() + '/'

HTTP_PROTOCOL = 'HTTP/1.1'

class Request(object):
    def __init__(self, header):
        self.request = ''
        self.uri = ''
        self.orig_uri = ''
        self.http_method = ''
        self.http_version = ''
        self.request_line = ''
        self.headers = defaultdict(list)
        self.content_length = -1
        self.body = ''
        self.query_string = ''

        self._parse(header)

    def _parse(self, header):
        lines = header.splitlines()
        self.request_line = lines[0]
        method, uri, protocol = self.request_line.split()

        self.orig_uri = self.uri = uri
        qpos = uri.find('?')
        if qpos != -1:
            self.query_string = uri[qpos + 1:]
            self.uri = uri[:qpos]

        self.http_method = method
        self.http_version = protocol 

        for i in range(1, len(lines)):
            key, value = lines[i].split(': ')
            self.headers[key].append(value)

        self.content_length = self.headers.get('Content-Length', [-1])[0]

class Response(object):
    RESPONSE_NONE = -1
    RESPONSE_UPDATE = 0
    RESPONSE_LOGIN = 1
    RESPONSE_BIDTYPE = 2
    RESPONSE_BULLETINS = 3
    RESPONSE_PRICE = 4

    def __init__(self):
        self.content_length = -1
        self.keepalive = False
        self.headers = defaultdict(list)
        self.response_type = Response.RESPONSE_NONE
        self.response = ''
        self.response_fd = -1

class Connection(object):
    def __init__(self, sockfd, remote_ip):
        self.sockfd = sockfd
        self.remote_ip = remote_ip
        self.keepalive = False
        self.thread = False

        self.reset()

    def reset(self):
        self.state = None
        self.keepalive = False
        self.http_status = -1
        self.request = None
        self.response = None
        self.thread = True
        self.environment = {}
        print("connection reset")

class ThreadRun(threading.Thread):
    def __init__(self, conn):
        threading.Thread.__init__(self)
        self.conn = conn
    def run(self):
        handle_connection(self.conn)
        self.conn.sockfd.close()
        print '[', self.getName(), ']', 'ended'

class MultiThreadServer(object): 
    def __init__(self, host, port):
        self.listenfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listenfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listenfd.bind((host, port))
        self.listenfd.listen(30)

    def serve_forver(self):
        again = 0
        inputs = [self.listenfd]
        while True:
            print("Enter serve_forver##############################################################")
            #READ_ONLY = select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR
            #READ_WRITE = (READ_ONLY | select.POLLOUT)
            #poller = select.poll()
            #poller.register(self.listenfd)

            #events = poller.poll(20)
            #for  fd ,flag in events:
            #    if flag & (select.POLLIN | select.POLLPRI):
            #        clientfd, clientaddr = self.listenfd.accept()
            #        print " Connection ", clientfd, clientaddr
            #    elif flag & select.POLLERR:
            #        print " ******exception on " , s.getpeername()
            #        poller.unregister(s)
            #        s.close()
            #        return
            #    else:
            #        again = 1

            #if again == 1:
            #    again = 0
            #    continue

            try:
                rs, ws, es = select.select(inputs, [], [])
                print("out select")
            except:
                print("select exception.")
                self.listenfd.close()
                return

            for r in rs:
                if r is self.listenfd:
                    clientfd, clientaddr = self.listenfd.accept()
                    print " Connection ", clientfd, clientaddr

            # select, fork or multithread
            conn = Connection(clientfd, clientaddr[0]) 

            th = ThreadRun(conn)
            th.start()

def get_header(buf):
    'return header and end pos of header'
    r = re.search(r'\r*\n\r*\n', buf)
    header = buf[:r.start()]
    return header, r.end()

####################

def read_request(conn):
    print '**[read_request]**'
    print("****************************************************")
    data = conn.sockfd.recv(4096)
    print(data)
    print("****************************************************")
    header, header_end_pos = get_header(data)
    #print(header)
    #print("-------------")
    #print(header_end_pos)
    #print("-------------")

    request = Request(header)

    if request.http_method == 'GET':
        weWant = int(request.content_length)
        weHad = len(data) - header_end_pos

        #print 'weWant', weWant
        #print 'weHad', weHad

        to_read = weWant - weHad

        body = data[header_end_pos:]
        if to_read > 0:
            print 'fuck' * 40
            tail = conn.sockfd.recv(to_read)
            body += tail

        request.body = body 

    conn.request = request

    #conn.keepalive = True if \
    #    request.headers.get('Connection', [''])[0].lower() == 'keep-alive' else False

def handle_request(conn):
    print '**[handle_request]**'
    filename = os.path.normpath(DOCUMENT_ROOT + conn.request.uri)
    print filename

    response = Response()
    response.headers['Server'].append('Apache-Coyote/1.1')

    file_status = os.stat(filename)
    print(file_status)
    # ok, it's a normal static file
    # privilege
    try:
        f = open(filename, 'rb')
    except IOError, e:
        print e
        return

    file_status = os.stat(filename)
    file_size = file_status[stat.ST_SIZE]
    modified_date = file_status[stat.ST_MTIME]
    response.response_fd = f
    response.content_length = file_size

    if filename.split('\\')[-2:-1] == ['clientupdate']:
        print("############ good, update")
        response.response_type = Response.RESPONSE_UPDATE
        response.headers['Last-Modified'].append('Sun, 01 Nov 2015 04:01:23 GMT')
        response.headers['Accept-Ranges'].append('bytes')
        response.headers['ETag'].append('W/"4405-1446782483150"')
        response.headers['Content-Length'].append(str(file_size))
    elif filename.split('\\')[-2:-1] == ['customer']:
        print("#######  customer function  ##########")
        response.headers['Content-Type'].append('application/json')
        response.headers['Transfer-Encoding'].append('chunked')
        if filename.split('\\')[-1:] == ['login']:
            print('##### login function ######')
            response.response_type = Response.RESPONSE_LOGIN
            conn.keepalive = True
        elif filename.split('\\')[-1:] == ['bidtype']:
            print('##### bidtype function ######')
            response.response_type = Response.RESPONSE_BIDTYPE
            conn.keepalive = True
        elif filename.split('\\')[-1:] == ['getbulletins']:
            print('##### bulletins function ######')
            response.response_type = Response.RESPONSE_BULLETINS
            conn.keepalive = True
        elif filename.split('\\')[-1:] == ['price']:
            print('##### price function ######')
            response.response_type = Response.RESPONSE_PRICE
            conn.keepalive = False

    response.headers['Date'].append('Thu, 12 Nov 2015 00:42:03 GMT')
    conn.http_status = 200
    conn.response = response

def response_request(conn):
    print '**[response_request]**'
    r = conn.response

    status_line = '%s %d %s\r\n' % (
        HTTP_PROTOCOL, conn.http_status, 'OK')
    headers = r.headers
    # headers = '\r\n'.join((': '.join((key, headers[key])) for key in headers))

    header_text = ''
    for key in headers:
        for v in headers[key]:
            header_text += ''.join((key, ': ', v, '\r\n'))
    header_text += '\r\n'

    print 'X' * 10
    send_data = ''

    send_data += status_line
    send_data += header_text
    if conn.response.response_type != Response.RESPONSE_UPDATE:
        send_data += str(hex(conn.response.content_length))[2:-1]

    send_data += '\r\n'
    while True:
        # UTF-8 encode
        data = r.response_fd.read(8192)
        if len(data) == 0: break
        send_data += data
    send_data += '\r\n'
    send_data += '0\r\n\r\n'
    conn.sockfd.send(send_data)
    r.response_fd.close()
    r.response_fd = -1

def handle_connection(conn):
    try:
        while True:
            conn.reset()

            read_request(conn)

            handle_request(conn)

            #if conn.keepalive:
            #    conn.response.headers['Connection'].append('Keep-Alive')
            #    conn.response.headers['Keep-Alive'].append('timeout=%d' % (timeout, ))

            response_request(conn)

            if not conn.keepalive:
                break
    except socket.error:
        print '{socket.error connection die}'
    except Exception, e:
        traceback.print_exc()

if __name__ == '__main__':

    server = MultiThreadServer(host, port)
    server.serve_forver()
