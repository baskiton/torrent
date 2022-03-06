import unittest as ut

from btorrent import Peer


class TestPeer(ut.TestCase):
    def setUp(self):
        self._peer = Peer('localhost', 123)
