import urllib.parse
import urllib.request

from typing import AnyStr, Dict, Sequence, Union

import torrent.transport.tracker as transport


class Tracker:
    def __init__(self, tracker_addr: bytes, proxies: Dict[str, str] = None) -> None:
        self.tracker_addr = urllib.parse.urlparse(tracker_addr)
        self.proxies: Dict[str, str] = proxies or {}
        self._proxy_handler = urllib.request.ProxyHandler(self.proxies)

        self.interval = 0
        self.last_announce_time = 0

    def __hash__(self):
        return hash(self.tracker_addr)

    def __eq__(self, other: 'Tracker') -> bool:
        return self.tracker_addr == other.tracker_addr

    def set_proxies(self, proxies: Dict[str, str]) -> None:
        self.proxies = proxies
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
