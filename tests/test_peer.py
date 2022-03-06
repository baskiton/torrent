import unittest as ut

from torrent.peer import Peer


class TestPeer(ut.TestCase):
    def setUp(self):
        self._peer = Peer('localhost', 123)
