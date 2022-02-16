import enum
import random
import secrets
import urllib.parse

from typing import Any, AnyStr

from torrent import Torrent, __version__


@enum.unique
class _TrackerEvent(enum.Enum):
    STARTED = 'started'
    STOPPED = 'stopped'
    COMPLETED = 'completed'


class Tracker:
    def __init__(self, torrent: Torrent) -> None:
        self.torrent = torrent
        self.interval = 0
        self.last_connecting_time = 0

        # tracker requests keys
        # self.info_hash
        self.peer_id = f'-PB{int(__version__.replace(".", "")[:4]):04}-'.encode() + secrets.token_bytes(12)
        self.port = 6881    # 6881-6889
        # self.ip =
        self.numwant = 30

        # shuffle urls in levels for first read
        # by BEP12: http://bittorrent.org/beps/bep_0012.html
        if torrent.metadata.announce_list:
            for lvl in torrent.metadata.announce_list:
                random.shuffle(lvl)

    def get_peers(self):
        peers = self._announce(_TrackerEvent.STARTED)

    def _announce(self, event: _TrackerEvent) -> Any:
        if self.torrent.metadata.announce_list:
            for lvl in self.torrent.metadata.announce_list:
                for idx, url in enumerate(lvl):
                    result = self._send_request(event, url)
                    if result:
                        lvl.pop(idx)
                        lvl.insert(0, url)
                        return result
        else:
            return self._send_request(event, self.torrent.metadata.announce)

    def _send_request(self, event: _TrackerEvent, url: AnyStr) -> Any:
        requests_keys = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': self.port,
            'uploaded': self.torrent.uploaded,
            'downloaded': self.torrent.downloaded,
            'left': self.torrent.left,
            'compact': 1,
        }
        u = urllib.parse.urlparse(url)
        if u.scheme == 'udp':
            # using UDP Tracker Protocol
            # BEP15: http://bittorrent.org/beps/bep_0015.html
            raise NotImplementedError
        elif u.scheme in ('http', 'https'):
            # using HTTP GET
            # BEP3: http://bittorrent.org/beps/bep_0003.html
            raise NotImplementedError
        else:
            raise ValueError(f'Unsupported url schema: {u.geturl()}')
