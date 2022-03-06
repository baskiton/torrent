import pathlib
import unittest as ut

import torrent


class TestTorrentClient(ut.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._client = torrent.Client()

    def setUp(self) -> None:
        self._torrent = torrent.Torrent(pathlib.Path('tests/files/test_0.torrent'))

    def test_add_torrent(self):
        self._client.add_torrent(self._torrent)
