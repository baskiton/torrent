import glob
import pathlib
import unittest as ut

import torrent


class TestTorrent(ut.TestCase):
    def test_file(self):
        for p in glob.iglob('tests/files/*.torrent'):
            fn = pathlib.Path(p)

            t = torrent.Torrent.from_file(fn)
            self.assertTrue(t, msg=f'"{fn}"')
            self.assertEqual(t.metadata.info.info_hash, t.info_hash)
