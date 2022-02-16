import random

from torrent import Torrent


class Tracker:
    def __init__(self, torrent: Torrent):
        self.torrent = torrent

        # shuffle urls in levels for first read
        for lvl in self.torrent.metadata.announce_list:
            random.shuffle(lvl)

    def get_peers(self):
        if self.torrent.metadata.announce_list:
            for lvl in self.torrent.metadata.announce_list:
                for idx, url in enumerate(lvl):
                    if ...:
                        lvl.pop(idx)
                        lvl.insert(0, url)
                        return ...
        # else:
        #     self.torrent.metadata.announce
        #     return ...
