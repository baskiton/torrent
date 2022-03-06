import pathlib
import unittest as ut

import btorrent


class TestTorrentClient(ut.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._client = btorrent.Client()

    def setUp(self) -> None:
        self._torrent = btorrent.Torrent(pathlib.Path('tests/files/test_0.torrent'))

    def test_add_torrent(self):
        self._client.add_torrent(self._torrent)

        self.assertIn(self._torrent, self._client.torrents)
        for lvl in self._torrent.announce_list:
            for tracker in lvl:
                self.assertIn(tracker, self._client.trackers)

    def test_set_proxy_ok(self):
        host, port = 'abc.com', 123
        proxies = (
            (host, port),
            (host, str(port)),
            (f'{host}:{port}', None),
        )
        tracker = btorrent.Tracker(b'http://testtracker/announce')

        for proxy_host, proxy_port in proxies:
            self._client.set_proxy(proxy_host, proxy_port)

            self.assertEqual(self._client.proxies['http'], f'{host}:{port}',
                             msg=f'{proxy_host}:{proxy_port}')
            for tracker in self._client.trackers:
                self.assertEqual(tracker.proxies['http'], f'{host}:{port}',
                                 msg=f'{proxy_host}:{proxy_port}')

        self._client.set_proxy()    # clear proxy

        self.assertIsNone(tracker.proxies.get('http'))
        for tracker in self._client.trackers:
            self.assertIsNone(tracker.proxies.get('http'))

    def test_set_proxy_fail(self):
        with self.assertRaises(ValueError):
            self._client.set_proxy('abc.com')
