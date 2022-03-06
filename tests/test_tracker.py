import unittest as ut

import btorrent


class TestTracker(ut.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._urls = (
            b'udp://aaa.bbb/ann',
            b'udp://aaa.bbb:123',
            b'http://aaa.bbb/announce',
            b'http://aaa.bbb:123/ann',
            b'https://aaa.bbb/ann',
            b'https://aaa.bbb:123/announce',
        )

    def setUp(self):
        self._trackers = [btorrent.Tracker(url) for url in self._urls]

    def test_announce(self):
        # TODO
        self.assertTrue(0)

    def test_scrape(self):
        # TODO
        self.assertTrue(0)
