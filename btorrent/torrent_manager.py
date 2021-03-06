import select
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Generator, Optional

import btorrent


class TorrentManager(threading.Thread):
    def __init__(self, torrent: btorrent.Torrent, client_peer_id: bytes,
                 port: int, udp_port: int, num_want: int,
                 ip: str = 0, reserved=0) -> None:
        super().__init__(daemon=True)
        self.torrent = torrent
        self.client_peer_id = client_peer_id
        self.ip, self.port, self.udp_port = ip, port, udp_port
        self.num_want = num_want
        self.reserved = reserved
        self.is_active = True

    def add_peer(self, peer: btorrent.Peer):
        self.torrent.add_peer(peer)

    def _get_actual_peers(self) -> Generator[Optional[btorrent.Peer], Any, None]:
        return (peer
                for peer in self.torrent.peers
                if (peer.fileno() > -1 and not peer.destroyed))

    def _handle_message(self, peer: btorrent.Peer, msg: btorrent.peer.transport.Message) -> None:
        print(f'{peer} handle {msg.__class__.__name__}')
        # TODO: check that this message is not a response for us

        if isinstance(msg, btorrent.peer.transport.KeepAlive):
            peer.do_keep_alive()

        elif isinstance(msg, btorrent.peer.transport.Handshake):
            if peer.peer_id and msg.peer_id and (peer.peer_id != msg.peer_id):
                # TODO: log it
                peer.disconnect()
            else:
                peer.peer_id = msg.peer_id
                peer.reserved = msg.reserved
                peer.handshaked = True
                peer.do_bitfield(self.torrent.bitfield)

        elif isinstance(msg, btorrent.peer.transport.Choke):
            peer.peer_choking = True

        elif isinstance(msg, btorrent.peer.transport.UnChoke):
            peer.peer_choking = False

        elif isinstance(msg, btorrent.peer.transport.Interested):
            peer.peer_interested = True
            peer.do_unchoke()

        elif isinstance(msg, btorrent.peer.transport.NotInterested):
            peer.peer_interested = False

        elif isinstance(msg, btorrent.peer.transport.Have):
            peer.bitfield[msg.piece_index] = 1

        elif isinstance(msg, btorrent.peer.transport.Bitfield):
            if not peer.bitfielded:
                peer.bitfield = msg.bitfield
                peer.bitfielded = True
            # peer.bitfield = msg.bitfield
            # peer.do_interested()

        elif isinstance(msg, btorrent.peer.transport.Request):
            pass

        elif isinstance(msg, btorrent.peer.transport.Piece):
            pass

        elif isinstance(msg, btorrent.peer.transport.Cancel):
            pass

        elif isinstance(msg, btorrent.peer.transport.Port):
            pass

    def run(self) -> None:
        self._start_download()

        while self.is_active:
            for peer in select.select(self._get_actual_peers(), [], [], 1)[0]:
                for msg in peer.get_message():
                    self._handle_message(peer, msg)
            self._announce(btorrent.tracker.transport.AnnounceEvent.NONE, self.num_want)

        self._stop_download()

    def stop(self):
        self.is_active = False

    def _announce(self, event=btorrent.tracker.transport.AnnounceEvent.NONE, num_want=0, force=False) -> None:
        if force or time.monotonic() > self.torrent.last_announce_time + self.torrent.interval:
            self.torrent.announce(event, self.client_peer_id, self.port, self.udp_port, num_want, self.ip)

    def _start_download(self) -> None:
        # TODO: STARTED is sent when a download first begins, but...
        self._announce(btorrent.tracker.transport.AnnounceEvent.STARTED, self.num_want)

        with ThreadPoolExecutor() as pool:
            pool.map(
                lambda peer: (
                    peer.connect(),
                    peer.do_handshake(self.torrent.info_hash, self.client_peer_id, self.reserved, True)
                ),
                self.torrent.peers
            )

    def _stop_download(self) -> None:
        for peer in self.torrent.peers:
            peer.disconnect()

        self._announce(btorrent.tracker.transport.AnnounceEvent.STOPPED, force=True)
