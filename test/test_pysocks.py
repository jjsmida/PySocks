from unittest import TestCase
from test_server import TestServer
#from test import socks4server
from threading import Thread
from multiprocessing import Process
import socks
import socket
import time
from pprint import pprint
import six
if six.PY3:
    import urllib.request as urllib2
else:
    import urllib2
from subprocess import Popen
import time

TEST_SERVER_HOST = '127.0.0.1'
TEST_SERVER_PORT = 7777
HTTP_PROXY_HOST = '127.0.0.1'
HTTP_PROXY_PORT = 7776
SOCKS4_PROXY_HOST = '127.0.0.1'
SOCKS4_PROXY_PORT = 7775
SOCKS5_PROXY_HOST = '127.0.0.1'
SOCKS5_PROXY_PORT = 7774
SOCKS5_SHADOWSOCKS_SERVER_PORT = 7773

def socks4_proxy_thread():
    #socks4server.run_proxy(port=SOCKS4_PROXY_PORT)
    cmd = 'python2.7 test/socks4server.py %d' % SOCKS4_PROXY_PORT
    server = Popen(cmd, shell=True)
    while True:
        res = server.poll()
        if res is not None:
            raise Exception('socks4server process has been terminated')


def http_proxy_thread():
    from test import httpproxy
    httpproxy.run_proxy(port=HTTP_PROXY_PORT)


def socks5_proxy_thread():
    client_cmd = 'sslocal -l %d -k bar -m rc4-md5 -s %s -p %d' % (
        SOCKS5_PROXY_PORT,
        SOCKS5_PROXY_HOST,
        SOCKS5_SHADOWSOCKS_SERVER_PORT,
    )
    client = Popen(client_cmd, shell=True)
    server_cmd = 'ssserver -s %s -k bar -p %d -m rc4-md5 --forbidden-ip ""' % (
        SOCKS5_PROXY_HOST,
        SOCKS5_SHADOWSOCKS_SERVER_PORT,
    )
    server = Popen(server_cmd, shell=True)
    while True:
        res = client.poll()
        if res is not None:
            raise Exception('Shadowsocks client has been terminated')

        res = server.poll()
        if res is not None:
            raise Exception('Shadowsocks server has been terminated')
        time.sleep(0.5)




class PySocksTestCase(TestCase):
    # TODO: move starting/stopping servers outsid TestCase
    # into runtest.py
    @classmethod
    def setUpClass(cls):
        try:
            cls.http_proxy = Process(target=http_proxy_thread)
            cls.http_proxy.daemon = True
            cls.http_proxy.start()

            cls.socks4_proxy = Process(target=socks4_proxy_thread)
            cls.socks4_proxy.daemon = True
            cls.socks4_proxy.start()

            cls.socks5_proxy = Process(target=socks5_proxy_thread)
            cls.socks5_proxy.daemon = True
            cls.socks5_proxy.start()

        except Exception as ex:
            #cls.test_server.stop()
            raise
        # Starting test_server later than http proxy server
        # because of "RuntimeError: IOLoop is already running" error
        cls.test_server = TestServer(address=TEST_SERVER_HOST,
                                     port=TEST_SERVER_PORT)
        cls.test_server.start()
        time.sleep(1)

    def setUp(self):
        self.test_server.reset()

    @classmethod
    def tearDownClass(cls):
        cls.test_server.stop()


    def test_foo(self):
        self.assertEqual('foo', 'fo' + 'o')

    def raw_http_request(self, host):
        return (
            'GET / HTTP/1.1\r\n'
            'Host: %s\r\n'
            'User-Agent: PySocksTester\r\n'
            'Accept: text/html\r\n'
            '\r\n' % host
        ).encode()

    # 0/13
    def test_stdlib_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.test_server.address, self.test_server.port))
        s.sendall(self.raw_http_request(TEST_SERVER_HOST))
        status = s.recv(2048).splitlines()[0]
        self.assertEqual(b'HTTP/1.1 200 OK', status)
        self.assertEqual('PySocksTester',
                         self.test_server.request['headers']['user-agent'])
        self.assertEqual(TEST_SERVER_HOST,
                         self.test_server.request['headers']['host'])


    # 1/13
    def test_http_proxy(self):
        self.test_server.response['data'] = b'zzz'
        s = socks.socksocket()
        s.set_proxy(socks.HTTP, HTTP_PROXY_HOST, HTTP_PROXY_PORT)
        s.connect((self.test_server.address, self.test_server.port))
        s.sendall(self.raw_http_request(TEST_SERVER_HOST))
        data = s.recv(2048)
        status = data.splitlines()[0]
        body = data.split(b'\r\n\r\n')[1]
        self.assertEqual(b'HTTP/1.1 200 OK', status)
        self.assertEqual('PySocksTester',
                         self.test_server.request['headers']['user-agent'])
        self.assertEqual(TEST_SERVER_HOST,
                         self.test_server.request['headers']['host'])
        self.assertEqual(b'zzz', body)


    # 2/13
    def test_socks4_proxy(self):
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS4, SOCKS4_PROXY_HOST, SOCKS4_PROXY_PORT)
        s.connect((self.test_server.address, self.test_server.port))
        s.sendall(self.raw_http_request(TEST_SERVER_HOST))
        status = s.recv(2048).splitlines()[0]
        self.assertEqual(b'HTTP/1.1 200 OK', status)
        self.assertEqual('PySocksTester',
                         self.test_server.request['headers']['user-agent'])
        self.assertEqual(TEST_SERVER_HOST,
                         self.test_server.request['headers']['host'])


    # 3/13
    def test_socks5_proxy(self):
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT)
        s.connect((self.test_server.address, self.test_server.port))
        s.sendall(self.raw_http_request(TEST_SERVER_HOST))
        status = s.recv(2048).splitlines()[0]
        self.assertEqual(b'HTTP/1.1 200 OK', status)
        self.assertEqual('PySocksTester',
                         self.test_server.request['headers']['user-agent'])
        self.assertEqual(TEST_SERVER_HOST,
                         self.test_server.request['headers']['host'])


    #def test_urllib2(self):
    #    # ?????????????
    #    # HTTPError: 405: Method Not Allowed
    #    # [*] Note: The HTTP proxy server may not be supported by PySocks
    #    # (must be a CONNECT tunnel proxy)
    #    socks.set_default_proxy(socks.HTTP, TEST_SERVER_HOST, TEST_SERVER_PORT)
    #    socks.wrap_module(urllib2)
    #    res = urllib2.urlopen(self.test_server.get_url())
    #    self.assertEqual(200, res.getcode())


#import sys
#sys.path.append("..")
#import socks
#import socket
#
#PY3K = sys.version_info[0] == 3
#
#if PY3K:
#    import urllib.request as urllib2
#else:
#    import sockshandler
#    import urllib2
#

#def SOCKS5_connect_timeout_test():
#    s = socks.socksocket()
#    s.settimeout(0.0001)
#    s.set_proxy(socks.SOCKS5, "8.8.8.8", 80)
#    try:
#        s.connect(("ifconfig.me", 80))
#    except socks.ProxyConnectionError as e:
#        assert str(e.socket_err) == "timed out"
#
#def SOCKS5_timeout_test():
#    s = socks.socksocket()
#    s.settimeout(0.0001)
#    s.set_proxy(socks.SOCKS5, "127.0.0.1", 1081)
#    try:
#        s.connect(("ifconfig.me", 4444))
#    except socks.GeneralProxyError as e:
#        assert str(e.socket_err) == "timed out"
#
#
#def socket_SOCKS5_auth_test():
#    # TODO: add support for this test. Will need a better SOCKS5 server.
#    s = socks.socksocket()
#    s.set_proxy(socks.SOCKS5, "127.0.0.1", 1081, username="a", password="b")
#    s.connect(("ifconfig.me", 80))
#    s.sendall(raw_HTTP_request())
#    status = s.recv(2048).splitlines()[0]
#    assert status.startswith(b"HTTP/1.1 200")
#
#def socket_HTTP_IP_test():
#    s = socks.socksocket()
#    s.set_proxy(socks.HTTP, "127.0.0.1", 8081)
#    s.connect(("133.242.129.236", 80))
#    s.sendall(raw_HTTP_request())
#    status = s.recv(2048).splitlines()[0]
#    assert status.startswith(b"HTTP/1.1 200")
#
#def socket_SOCKS4_IP_test():
#    s = socks.socksocket()
#    s.set_proxy(socks.SOCKS4, "127.0.0.1", 1080)
#    s.connect(("133.242.129.236", 80))
#    s.sendall(raw_HTTP_request())
#    status = s.recv(2048).splitlines()[0]
#    assert status.startswith(b"HTTP/1.1 200")
#
#def socket_SOCKS5_IP_test():
#    s = socks.socksocket()
#    s.set_proxy(socks.SOCKS5, "127.0.0.1", 1081)
#    s.connect(("133.242.129.236", 80))
#    s.sendall(raw_HTTP_request())
#    status = s.recv(2048).splitlines()[0]
#    assert status.startswith(b"HTTP/1.1 200")
#
#def urllib2_SOCKS5_test():
#    socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 1081)
#    socks.wrap_module(urllib2)
#    status = urllib2.urlopen("http://ifconfig.me/ip").getcode()
#    assert status == 200
#
#def urllib2_handler_HTTP_test():
#    import sockshandler
#    opener = urllib2.build_opener(sockshandler.SocksiPyHandler(socks.HTTP, "127.0.0.1", 8081))
#    status = opener.open("http://ifconfig.me/ip").getcode()
#    assert status == 200
#
#def urllib2_handler_SOCKS5_test():
#    import sockshandler
#    opener = urllib2.build_opener(sockshandler.SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 1081))
#    status = opener.open("http://ifconfig.me/ip").getcode()
#    assert status == 200
#
#def global_override_HTTP_test():
#    socks.set_default_proxy(socks.HTTP, "127.0.0.1", 8081)
#    good = socket.socket
#    socket.socket = socks.socksocket
#    status = urllib2.urlopen("http://ifconfig.me/ip").getcode()
#    socket.socket = good
#    assert status == 200
#
#def global_override_SOCKS5_test():
#    default_proxy = (socks.SOCKS5, "127.0.0.1", 1081)
#    socks.set_default_proxy(*default_proxy)
#    good = socket.socket
#    socket.socket = socks.socksocket
#    status = urllib2.urlopen("http://ifconfig.me/ip").getcode()
#    socket.socket = good
#    assert status == 200
#    assert socks.get_default_proxy()[1].decode() == default_proxy[1]
#
#def bail_early_with_ipv6_test():
#    sock = socks.socksocket()
#    ipv6_tuple = addr, port, flowinfo, scopeid = "::1", 1234, 0, 0
#    try:
#        sock.connect(ipv6_tuple)
#    except socket.error:
#        return
#    else:
#        assert False, "was expecting"
#
#def main():
#    print("Running tests...")
#    socket_HTTP_test()
#    print("1/13")
#    socket_SOCKS4_test()
#    print("2/13")
#    socket_SOCKS5_test()
#    print("3/13")
#    if not PY3K:
#        urllib2_handler_HTTP_test()
#        print("3.33/13")
#        urllib2_handler_SOCKS5_test()
#        print("3.66/13")
#    socket_HTTP_IP_test()
#    print("4/13")
#    socket_SOCKS4_IP_test()
#    print("5/13")
#    socket_SOCKS5_IP_test()
#    print("6/13")
#    SOCKS5_connect_timeout_test()
#    print("7/13")
#    SOCKS5_timeout_test()
#    print("8/13")
#    urllib2_HTTP_test()
#    print("9/13")
#    urllib2_SOCKS5_test()
#    print("10/13")
#    global_override_HTTP_test()
#    print("11/13")
#    global_override_SOCKS5_test()
#    print("12/13")
#    bail_early_with_ipv6_test()
#    print("13/13")
#    print("All tests ran successfully")
#
#
#if __name__ == "__main__":
#    main()
