import unittest
import urllib.parse

from torrent import transport


class TestTransportTracker(unittest.TestCase):
    def test_http_request(self):
        u = urllib.parse.urlparse('http://aaa.b/announce')
        params = {}

        self.assertTrue(0)

    def test_udp_request(self):
        u = urllib.parse.urlparse('udp://aaa.b/announce')

        self.assertTrue(0)


class TestTransportPeer(unittest.TestCase):
    def test_utp(self):
        self.assertTrue(transport.peer.UTP())
