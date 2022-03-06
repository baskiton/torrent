import glob
import pathlib
import unittest as ut

import torrent


class TestTorrent(ut.TestCase):
    def test_torrent(self):
        path = pathlib.Path('tests/files/test_0.torrent')
        tt_0 = torrent.Torrent(torrent.TorrentFile.from_file(path))
        tt_1 = torrent.Torrent(path)

        for ilvl, lvl in enumerate(tt_0.announce_list):
            for itrk, tracker in enumerate(lvl):
                self.assertEqual(tracker.tracker_addr,
                                 tt_1.announce_list[ilvl][itrk].tracker_addr)
