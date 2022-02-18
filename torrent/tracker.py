import enum
import random
import secrets
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from typing import Any, AnyStr, Dict, List

from torrent import Peer, Torrent, transport


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
        self.peers: Dict[int, Peer] = {}

        # tracker requests keys
        # self.info_hash
        self.peer_id = f'-bPB-'.encode() + secrets.token_bytes(11)
        self.port = 6881    # 6881-6889
        # self.ip =
        self.numwant = 30

        self.announce_list = []
        if torrent.metadata.announce_list:
            for lvl in torrent.metadata.announce_list:
                x = []
                # shuffle urls in levels for first read
                # by BEP12: http://bittorrent.org/beps/bep_0012.html
                random.shuffle(lvl)
                for announce in lvl:
                    x.append(transport.tracker.TrackerTransport(announce))
        else:
            self.announce_list.append([transport.tracker.TrackerTransport(torrent.metadata.announce)])

    def get_peers(self):
        response = self._announce(_TrackerEvent.STARTED)
        if isinstance(response, dict):
            peers = response.get(b'peers')
            if isinstance(peers, bytes):
                # compact model
                self._peers_compact_parse(peers)
            elif isinstance(peers, list):
                # dictionary model
                self._peers_dict_parse(peers)

    def _announce(self, event: _TrackerEvent) -> Any:
        if self.torrent.metadata.announce_list:
            for lvl in self.torrent.metadata.announce_list:
                for idx, url in enumerate(lvl):
                    result = self._send_request(event, url.decode('utf8'))
                    if result:
                        lvl.pop(idx)
                        lvl.insert(0, url)
                        self.last_connecting_time = time.time()
                        return result
        else:
            return self._send_request(event, self.torrent.metadata.announce)

    def _send_request(self, event: _TrackerEvent, url: AnyStr) -> Any:
        u = urllib.parse.urlparse(url)
        if u.scheme == 'udp':
            #TODO:
            # using UDP Tracker Protocol
            # BEP15: http://bittorrent.org/beps/bep_0015.html
            return transport.tracker.udp_request(u)

        elif u.scheme in ('http', 'https'):
            # using HTTP GET
            # BEP3: http://bittorrent.org/beps/bep_0003.html
            requests_keys = {
                'info_hash': self.torrent.info_hash,
                'peer_id': self.peer_id,
                'downloaded': self.torrent.downloaded,
                'left': self.torrent.left,
                'uploaded': self.torrent.uploaded,
                'event': event,
                # 'ip': ,
                # 'key': ,
                'numwant': self.numwant,
                'port': self.port,
                'compact': 1,
            }
            return transport.tracker.http_request(u, requests_keys)

        raise ValueError(f'Unsupported url scheme: {u.geturl()}')

    def _peers_compact_parse(self, peers: bytes):
        for ip, port in struct.iter_unpack('!IH', peers):
            p = Peer(ip, port)
            # check if this peer already in self.peers
            self.peers[p.id] = p

    def _peers_dict_parse(self, peers: List[Dict]):
        for peer in peers:
            p = Peer(peer.get(b'ip'), peer.get(b'port'), peer.get(b'peer id'))
            # check if this peer already in self.peers
            self.peers[p.id] = p
