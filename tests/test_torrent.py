import glob
import pathlib
import unittest as ut

import torrent


class TestTorrent(ut.TestCase):
    def test_file(self):
        for p in glob.iglob('tests/files/*.torrent'):
            fn = pathlib.Path(p)

            self.assertTrue(torrent.Torrent.from_file(fn), msg=f'"{fn}"')
