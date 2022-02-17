import hashlib
import pathlib
import unittest as ut

import torrent


class TestTracker(ut.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._urls = (
            'udp://aaa.bbb/ann',
            'udp://aaa.bbb:123',
            'http://aaa.bbb/announce',
            'http://aaa.bbb:123/ann',
            'https://aaa.bbb/ann',
            'https://aaa.bbb:123/announce',
        )
        _piece_len = 4
        _file_content = b'hello, world!\n'
        _file = {
            'content': _file_content,
            'path': pathlib.Path('abc.txt'),
            'length': len(_file_content),
            'md5sum': hashlib.md5(_file_content).digest(),
        }
        _info_pieces = b''.join(hashlib.sha1(_file_content[i:i+_piece_len]).digest()
                                for i in range(0, len(_file_content), _piece_len))
        cls._metadata = {
            b'announce': cls._urls[0].encode(),
            b'announce list': [
                [cls._urls[1].encode(), cls._urls[2].encode()],
                [cls._urls[3].encode(), cls._urls[4].encode()],
                [cls._urls[5].encode()],
            ],
            b'info': {
                b'pieces': _info_pieces,
                b'piece length': _piece_len,
                b'name': str(_file['path']).encode(),
                b'length': _file['length'],
            }
        }

    def setUp(self):
        self._t_metadata = torrent.metadata.TorrentMetadata(self._metadata)
        self._torrent = torrent.Torrent(self._t_metadata)
        self._tracker = torrent.Tracker(self._torrent)

    def test_get_peers(self):
        self.assertTrue(0)

    def test_announce(self):
        self.assertTrue(self._tracker._announce(torrent.tracker._TrackerEvent.STOPPED))

    def test_send_request(self):
        for url in self._urls:
            for evt in torrent.tracker._TrackerEvent:
                self.assertTrue(self._tracker._send_request(evt._value_, url))
