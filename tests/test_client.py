import pathlib
import unittest as ut

import btorrent

DATA_DIR = pathlib.Path('tests/tmp')
CFG_FILE = pathlib.Path(DATA_DIR / btorrent.Config._CONFIG_FILE)
btorrent.Client._DATA_DIR = DATA_DIR


class TestTorrentConfig(ut.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        CFG_FILE.unlink(True)
        DATA_DIR.rmdir()

    def test_and_save(self):
        cfg0 = btorrent.Config(DATA_DIR)
        cfg0.port = 1234
        cfg0.udp_port = 5678
        cfg0.num_want = 40
        cfg0.proxies = {'abc': 'def'}
        cfg0.save_options()

        cfg1 = btorrent.Config(DATA_DIR)

        self.assertEqual(1234, cfg1.port)
        self.assertEqual(5678, cfg1.udp_port)
        self.assertEqual(40, cfg1.num_want)
        self.assertDictEqual({'abc': 'def'}, dict(cfg1.proxies))


class TestTorrentClient(ut.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._client = btorrent.Client()

    @classmethod
    def tearDownClass(cls) -> None:
        CFG_FILE.unlink(True)
        DATA_DIR.rmdir()

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
                             msg=f'{proxy_host}:{proxy_port} <=> {self._client.proxies}')
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
