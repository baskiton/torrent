import unittest

from torrent.peer import Peer


class TestPeer(unittest.TestCase):
    def setUp(self):
        self._peer = Peer('localhost', 123)
