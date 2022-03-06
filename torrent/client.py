import secrets

from typing import Sequence

import torrent


class Client:
    def __init__(self):
        self.__trackers = set()
        self.__torrents = set()

        # settings
        peer_prefix = f'-bPB{torrent.__version__}-'.encode('ascii')
        self.peer_id = peer_prefix + secrets.token_bytes(20 - len(peer_prefix))
        self.port = 6881    # 6881-6889
        self.udp_port = 8881    # 8881-8889
        # self.ip =
        self.numwant = 5

    def add_torrent(self, t: torrent.Torrent):
        pass

    def set_proxy(self):
        pass
