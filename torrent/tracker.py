import urllib.parse
import urllib.request

from typing import AnyStr, Dict, Sequence, Union

import torrent.transport.tracker as transport


class Tracker:
    def __init__(self, tracker_addr: bytes, proxies: Dict[str, str] = None) -> None:
        self.tracker_addr = urllib.parse.urlparse(tracker_addr)
        self.proxies = proxies or {}
        self._proxy_handler = urllib.request.ProxyHandler(self.proxies)

        self.interval = 0
        self.last_announce_time = 0

    def set_proxy(self, host: str, port: Union[int, AnyStr] = None) -> None:
        """
        >>> x = Tracker(...)
        >>> x.set_proxy('abc.com', 123)
        >>> x.set_proxy('abc.com', '123')
        >>> x.set_proxy('abc.com:123')
        >>> x.set_proxy('abc.com')
        ValueError: Port not specified
        """

        if not host:
            raise ValueError('Host is not specified')

        if port is None:
            if host.find(':') == -1:
                raise ValueError('Port is not specified')
        else:
            host = f'{host}:{port}'

        self.proxies['http'] = host
        self.add_proxy({'http': host})

    # def set_socks(self, host: str, port: Union[int, AnyStr] = None,
    #               user: str = None, password: str = None,
    #               version: Union[int, AnyStr] = 5):

    def add_proxy(self, proxies: Dict[str, str]) -> None:
        self.proxies.update(proxies)
        self._proxy_handler.__init__(self.proxies)

    def clear_proxy(self, type: str) -> None:
        self.proxies.pop(type)
        self._proxy_handler.__init__(self.proxies)

    def _send_request(self, req: transport.Request) -> transport.Response:
        opener = transport.build_opener(self._proxy_handler)
        r = opener.open(req.get_req())
        if isinstance(r, transport.ErrorResponse):
            raise r
        return r

    def announce(self,
                 info_hash: bytes,
                 peer_id: bytes,
                 left: int,
                 downloaded=0,
                 uploaded=0,
                 event=transport.AnnounceEvent.NONE,
                 key=-1,
                 numwant=-1,
                 ip=0,
                 port=6881,
                 udp_port=8881) -> Union[transport.Response, transport.AnnounceResponse]:
        if self.tracker_addr.scheme == b'udp':
            port = udp_port
        return self._send_request(transport.AnnounceRequest(
            self.tracker_addr, info_hash, peer_id,
            downloaded, left, uploaded, event,
            key, numwant, ip, port
        ))

    def scrape(self, info_hashes: Sequence[bytes] = ()) -> Union[transport.Response, transport.ScrapeResponse]:
        return self._send_request(transport.ScrapeRequest(self.tracker_addr, info_hashes))
