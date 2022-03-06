import glob
import pathlib
import unittest as ut

import torrent


class TestTorrentFile(ut.TestCase):
    def test_file(self):
        for p in glob.iglob('tests/files/test_*.torrent'):
            fn = pathlib.Path(p)

            t = torrent.TorrentFile.from_file(fn)
            self.assertTrue(t, msg=f'"{fn}"')
            self.assertEqual(t.metadata.info.info_hash, t.info_hash)
