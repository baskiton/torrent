import enum
import random
import secrets
import time

from typing import Any, AnyStr, Callable, Dict, Union

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
        self.seeders = 0
        self.leechers = 0
        self.proxies = {}

        # tracker requests keys
        # self.info_hash
        self.peer_id = f'-bPB-'.encode() + secrets.token_bytes(11)
        self.port = 6881    # 6881-6889
        self.udp_port = 8881    # 8881-8889
        # self.ip =
        self.numwant = 5

        self.announce_list = []
        if torrent.metadata.announce_list:
            for lvl in torrent.metadata.announce_list:
                x = []
                # shuffle urls in levels for first read
                # by BEP12: http://bittorrent.org/beps/bep_0012.html
                random.shuffle(lvl)
                for announce in lvl:
                    x.append(transport.tracker.TrackerTransport(announce, self.proxies))
                self.announce_list.append(x)
        else:
            self.announce_list.append([transport.tracker.TrackerTransport(torrent.metadata.announce, self.proxies)])

    def set_proxy(self, host: str, port: Union[int, AnyStr] = None):
        """
        >>> x = Tracker()
        >>> x.set_proxy('abc.com', 123)
        >>> x.set_proxy('abc.com', '123')
        >>> x.set_proxy('abc.com:123')
        >>> x.set_proxy('abc.com')
        ValueError: Port not specified
        """

        if port is None:
            if host.find(':') == -1:
                raise ValueError('Port not specified')
        else:
            host = f'{host}:{port}'
        self.proxies['http'] = host
        for lvl in self.announce_list:
            for t in lvl:
                t.add_proxy({'http': host})

    # def set_socks(self, host: str, port: Union[int, AnyStr] = None,
    #               user: str = None, password: str = None,
    #               version: Union[int, AnyStr] = 5):

    def _send_request(self, trt_meth: Callable, **params) -> Any:
        for lvl in self.announce_list:
            for idx, trt in enumerate(lvl):
                params['port'] = self.udp_port if trt.tracker_addr.scheme == b'udp' else self.port
                try:
                    result = trt_meth(trt, **params)
                except (ConnectionError, OSError) as e:
                    # TODO: log it
                    print(f'{e.__class__.__name__}: "{e}" for '
                          f'"{trt.tracker_addr.geturl().decode("ascii")}"')
                    continue
                if result:
                    lvl.pop(idx)
                    lvl.insert(0, trt)
                    self.last_connecting_time = time.time()
                    return result

    def get_peers(self):
        response: transport.tracker.AnnounceResponse = self._send_request(
            transport.tracker.TrackerTransport.announce,
            info_hash=self.torrent.info_hash,
            peer_id=self.peer_id,
            downloaded=self.torrent.downloaded,
            left=self.torrent.left,
            uploaded=self.torrent.uploaded,
            # event=transport.tracker.AnnounceEvent.STARTED,
            # key=key,
            numwant=self.numwant,
            # ip=ip,
            # port=self.port
        )
        if response:
            # TODO
            self.interval = response.interval
            self.seeders = response.seeders
            self.leechers = response.leechers
            for peer in response.peers:
                # check if this peer already in self.peers
                self.peers[peer.id] = peer
            return response.peers
