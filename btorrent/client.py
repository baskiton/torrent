import appdirs
import configparser
import pathlib
import secrets

from typing import AnyStr, Dict, List, Set, Union

import btorrent


class Config:
    _CONFIG_FILE_NAME = 'config.ini'

    _NETWORK = 'Network'
    _PROXIES = 'Proxies'

    def __init__(self, cfg_dir: pathlib.Path):
        self.config = configparser.ConfigParser(allow_no_value=True)
        self.config_file = cfg_dir / self._CONFIG_FILE_NAME

        # default options
        self.config.add_section(self._NETWORK)
        self.port = 6881
        self.udp_port = 8881
        self.num_want = 5

        self.config.add_section(self._PROXIES)

        self.config.read(self.config_file)

        self.save_options()

    def save_options(self):
        with self.config_file.open('w') as f:
            self.config.write(f)

    @property
    def port(self) -> int:
        return self.config.getint(self._NETWORK, 'port')

    @port.setter
    def port(self, val: int) -> None:
        self.config.set(self._NETWORK, 'port', str(val))

    @property
    def udp_port(self) -> int:
        return self.config.getint(self._NETWORK, 'udp_port')

    @udp_port.setter
    def udp_port(self, val: int) -> None:
        self.config.set(self._NETWORK, 'udp_port', str(val))

    @property
    def num_want(self) -> int:
        return self.config.getint(self._NETWORK, 'num_want')

    @num_want.setter
    def num_want(self, val: int) -> None:
        self.config.set(self._NETWORK, 'num_want', str(val))

    @property
    def proxies(self) -> configparser.SectionProxy:
        return self.config[self._PROXIES]

    @proxies.setter
    def proxies(self, val: Dict[str, str]) -> None:
        self.config[self._PROXIES] = val


class Client:
    _APP_DIRS = appdirs.AppDirs(btorrent.__app_name__)
    _DATA_DIR = pathlib.Path(_APP_DIRS.user_data_dir)

    def __init__(self) -> None:
        self.__trackers: Set[btorrent.Tracker] = set()
        self.__torrents: List[btorrent.Torrent] = []

        peer_prefix = f'-bT{btorrent.__version__}-'.encode('ascii')
        self.peer_id = peer_prefix + secrets.token_bytes(20 - len(peer_prefix))

        self._DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.config = Config(self._DATA_DIR)

    @property
    def trackers(self) -> Set[btorrent.Tracker]:
        return self.__trackers

    @property
    def torrents(self) -> List[btorrent.Torrent]:
        return self.__torrents

    @property
    def proxies(self) -> configparser.SectionProxy:
        return self.config.proxies

    @proxies.setter
    def proxies(self, val: Dict[str, str]) -> None:
        self.config.proxies = val

    def add_torrent(self, t: btorrent.Torrent) -> None:
        if t not in self.__torrents:
            # TODO: add torrent-data to data directory
            self.__torrents.append(t)
            for lvl in t.announce_list:
                for tracker in lvl:
                    tracker.set_proxies(self.proxies)
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
            self.proxies.update({'http': host})
        else:   # clear proxy
            self.proxies.pop('http')

        self._upd_proxy()

    # def set_socks(self, host: str, port: Union[int, AnyStr] = None,
    #               user: str = None, password: str = None,
    #               version: Union[int, AnyStr] = 5):

    def _upd_proxy(self) -> None:
        self.config.save_options()
        for tracker in self.__trackers:
            tracker.set_proxies(self.proxies)
