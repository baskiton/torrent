import unittest as ut

import torrent


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
        self._trackers = [torrent.Tracker(url) for url in self._urls]

    def test_proxy_ok(self):
        host, port = 'abc.com', 123
        proxies = (
            (host, port),
            (host, str(port)),
            (f'{host}:{port}', None),
        )
        tracker = torrent.Tracker(b'http://testtracker/announce')

        for proxy_host, proxy_port in proxies:
            tracker.set_proxy(proxy_host, proxy_port)
            self.assertEqual(tracker.proxies['http'], 'abc.com:123',
                             msg=f'{proxy_host}:{proxy_port}')

        tracker.clear_proxy('http')
        self.assertIsNone(tracker.proxies.get('http'))

    def test_set_proxy_fail(self):
        tracker = torrent.Tracker(b'http://testtracker/announce')

        with self.assertRaises(ValueError):
            tracker.set_proxy('abc.com')

        with self.assertRaises(ValueError):
            tracker.set_proxy(None)

    def test_announce(self):
        # TODO
        self.assertTrue(0)

    def test_scrape(self):
        # TODO
        self.assertTrue(0)
