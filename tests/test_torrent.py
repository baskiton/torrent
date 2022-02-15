import pathlib
import unittest as ut

import torrent


class TestTorrent(ut.TestCase):
    def test_file(self):
        fn = pathlib.Path('tests/files/test_0.torrent')

        self.assertTrue(torrent.Torrent.from_file(fn), fn)
