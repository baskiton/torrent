import pathlib
import random
import select
import time

from typing import Any, Callable, List, Set, Union

import bitstring

import btorrent


class Torrent:
    def __init__(self, tfile: Union[pathlib.Path, btorrent.TorrentFile]) -> None:
        if isinstance(tfile, pathlib.Path):
            tfile = btorrent.TorrentFile.from_file(tfile)

        self.peers: Set[btorrent.Peer] = set()
        self.announce_list: List[List[btorrent.tracker.Tracker]] = []
        self.tfile = tfile

        self.uploaded = 0
        self.downloaded = 0
        self.left = tfile.total_size
        self.bitfield = bitstring.BitArray(tfile.metadata.info.pieces_amount)

        self.seeders = 0
        self.leechers = 0
        self.interval = 0
        self.last_announce_time = 0

        if tfile.metadata.announce_list:
            for lvl in tfile.metadata.announce_list:
                x = []
                # shuffle urls in levels for first read
                # by BEP12: http://bittorrent.org/beps/bep_0012.html
                random.shuffle(lvl)
                for url in lvl:
                    x.append(btorrent.tracker.Tracker(url))
                self.announce_list.append(x)
        else:
            self.announce_list.append([btorrent.tracker.Tracker(tfile.metadata.announce)])

    @property
    def file_name(self):
        return self.tfile.file_name

    @property
    def info_hash(self) -> bytes:
        return self.tfile.info_hash

    def __eq__(self, other: 'Torrent') -> bool:
        return self.info_hash == other.info_hash

    def add_peer(self, peer: btorrent.Peer):
        self.peers.add(peer)

    def _send_request(self, trt_meth: Callable, **params) -> Any:
        for lvl in self.announce_list:
            for idx, tracker in enumerate(lvl):
                try:
                    result = trt_meth(tracker, **params)
                except (ConnectionError, OSError) as e:
                    # TODO: log it
                    print(f'{e.__class__.__name__}: "{e}" for '
                          f'<{tracker.tracker_addr.geturl().decode("ascii")}>')
                    continue

                if result:
                    lvl.pop(idx)
                    lvl.insert(0, tracker)
                    return result

    def announce(self, event: btorrent.tracker.transport.AnnounceEvent, peer_id: bytes,
                 port: int, udp_port: int, num_want: int, ip: str = 0) -> None:
        response: btorrent.tracker.transport.AnnounceResponse = self._send_request(
            btorrent.tracker.Tracker.announce,
            event=event,
            port=port,
            udp_port=udp_port,
            info_hash=self.info_hash,
            peer_id=peer_id,
            downloaded=self.downloaded,
            left=self.left,
            uploaded=self.uploaded,
            numwant=num_want,
            ip=ip,
            # key=key,
        )
        if response is not None:
            self.last_announce_time = time.monotonic()
            self.interval = response.interval
            self.seeders = response.seeders
            self.leechers = response.leechers

            # `peer` is not added if already in `self.peers`
            self.peers.update(map(lambda x: btorrent.Peer(*x), response.peers))
