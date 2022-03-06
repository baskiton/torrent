import pathlib
import random
import time

from typing import Any, Callable, List, Set, Union

import torrent


class Torrent:
    def __init__(self, tfile: Union[pathlib.Path, torrent.TorrentFile]) -> None:
        if isinstance(tfile, pathlib.Path):
            tfile = torrent.TorrentFile.from_file(tfile)

        self.peers: Set[torrent.Peer] = set()
        self.announce_list: List[List[torrent.tracker.Tracker]] = []
        self.tfile = tfile

        self.uploaded = 0
        self.downloaded = 0
        self.left = tfile.total_size

        self.seeders = 0
        self.leechers = 0
        self.interval = 0
        self.last_connecting_time = 0

        if tfile.metadata.announce_list:
            for lvl in tfile.metadata.announce_list:
                x = []
                # shuffle urls in levels for first read
                # by BEP12: http://bittorrent.org/beps/bep_0012.html
                random.shuffle(lvl)
                for url in lvl:
                    x.append(torrent.tracker.Tracker(url))
                self.announce_list.append(x)
        else:
            self.announce_list.append([torrent.tracker.Tracker(tfile.metadata.announce)])

    @property
    def id(self) -> bytes:
        return self.tfile.info_hash

    def __eq__(self, other: 'Torrent') -> bool:
        return self.id == other.id

    def start_download(self, peer_id: bytes, ip: str, port: int, udp_port: int, num_want: int):
        # TODO: STARTED is sent when a download first begins
        event = torrent.tracker.transport.AnnounceEvent.NONE

        self._announce(event, peer_id, ip, port, udp_port, num_want)
        # TODO: ...

    def stop_download(self, peer_id: bytes, ip: str, port: int, udp_port: int):
        # TODO: close all connections with peers

        self._announce(torrent.tracker.transport.AnnounceEvent.STOPPED, peer_id, ip, port, udp_port, 0)

    def pause_download(self):
        pass

    def _send_request(self, trt_meth: Callable, **params) -> Any:
        for lvl in self.announce_list:
            for idx, tracker in enumerate(lvl):
                try:
                    result = trt_meth(tracker, **params)
                except (ConnectionError, OSError) as e:
                    # TODO: log it
                    print(f'{e.__class__.__name__}: "{e}" for '
                          f'"{tracker.tracker_addr.geturl().decode("ascii")}"')
                    continue
                if result:
                    lvl.pop(idx)
                    lvl.insert(0, tracker)
                    return result

    def _announce(self, event: torrent.tracker.transport.AnnounceEvent, peer_id: bytes,
                  ip: str, port: int, udp_port: int, num_want: int) -> None:
        response: torrent.tracker.transport.AnnounceResponse = self._send_request(
            torrent.tracker.Tracker.announce,
            event=event,
            port=port,
            udp_port=udp_port,
            info_hash=self.tfile.info_hash,
            peer_id=peer_id,
            downloaded=self.downloaded,
            left=self.left,
            uploaded=self.uploaded,
            numwant=num_want,
            ip=ip,
            # key=key,
        )
        if response is not None:
            self.last_connecting_time = time.time()
            self.interval = response.interval
            self.seeders = response.seeders
            self.leechers = response.leechers
            self.peers.update(response.peers)   # `peer` is not added if already in `self.peers`
