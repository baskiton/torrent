import unittest as ut

import torrent


class TestTorrent(ut.TestCase):
    def test_file(self):
        fn = 'tests/files/SimCity 4 Deluxe Edition [GOG] [RUS ENG MULTI7] [rutracker-5305145].torrent'

        self.assertTrue(torrent.Torrent.from_file(fn), fn)
