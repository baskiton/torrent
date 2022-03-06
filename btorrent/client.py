import secrets

from typing import AnyStr, Dict, List, Set, Union

import btorrent


class Client:
    def __init__(self) -> None:
        self.__trackers: Set[btorrent.Tracker] = set()
        self.__torrents: List[btorrent.Torrent] = []
        self.__proxies: Dict[str, str] = {}

        # settings
        peer_prefix = f'-bPB{btorrent.__version__}-'.encode('ascii')
        self.peer_id = peer_prefix + secrets.token_bytes(20 - len(peer_prefix))
        self.port = 6881    # 6881-6889
        self.udp_port = 8881    # 8881-8889
        # self.ip =
        self.numwant = 5

    @property
    def trackers(self):
        return self.__trackers

    @property
    def torrents(self):
        return self.__torrents

    @property
    def proxies(self):
        return self.__proxies

    def add_torrent(self, t: btorrent.Torrent) -> None:
        if t not in self.__torrents:
            self.__torrents.append(t)
            for lvl in t.announce_list:
                for tracker in lvl:
                    tracker.set_proxies(self.__proxies)
                    self.__trackers.add(tracker)

    def set_proxy(self, host: str = None, port: Union[int, AnyStr] = None) -> None:
        """
        >>> x = Client()
        >>> x.set_proxy('abc.com', 123)
        >>> x.set_proxy('abc.com', '123')
        >>> x.set_proxy('abc.com:123')
        >>> x.set_proxy('abc.com')
        ValueError: Port not specified
        >>> x.set_proxy()   # clear proxy
        """

        if host:
            if port is None:
                if host.find(':') == -1:
                    raise ValueError('Port is not specified')
            else:
                host = f'{host}:{port}'
            self.__proxies.update({'http': host})
        else:   # clear proxy
            self.__proxies.pop('http')

        self._upd_proxy()

    # def set_socks(self, host: str, port: Union[int, AnyStr] = None,
    #               user: str = None, password: str = None,
    #               version: Union[int, AnyStr] = 5):

    def _upd_proxy(self) -> None:
        for tracker in self.__trackers:
            tracker.set_proxies(self.__proxies)
