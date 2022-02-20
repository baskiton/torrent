__all__ = (
    'AnnounceResponse', 'ConnectResponse', 'ErrorResponse', 'ScrapeResponse',
    'AnnounceEvent', 'TrackerTransport'
)

import enum
import http.client
import secrets
import socket as sk
import struct
import time
import urllib.parse
import urllib.request

from collections import namedtuple as nt
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

import torrent
from torrent import __version__, bencode


@enum.unique
class AnnounceEvent(enum.IntEnum):
    NONE = 0
    COMPLETED = 1
    STARTED = 2
    STOPPED = 3


@enum.unique
class _TPReqType(enum.IntEnum):
    CONNECT = 0
    ANNOUNCE = 1
    SCRAPE = 2
    ERROR = 3


class _Request:
    ACTION = _TPReqType.CONNECT
    _COMMON_REQ_FMT = '!QII'
    _REQ_FMT = ''

    def __init__(self,
                 url: urllib.parse.ParseResultBytes,
                 connection_id: int = None,
                 dynamic_cid=True,
                 **params):
        self.url = url
        self.connection_id = connection_id
        self.dynamic_cid = dynamic_cid
        self.transaction_id = None
        self.params = params

    def http(self) -> urllib.request.Request:
        """
        using HTTP GET
        BEP3: http://bittorrent.org/beps/bep_0003.html
        """

        req = urllib.request.Request(f'{self.url.geturl().decode("ascii")}'
                                     f'{self.url.query and "&" or "?"}'
                                     f'{urllib.parse.urlencode(self.params)}',
                                     method='GET')
        req.add_header('User-agent', f'pyTorrent/{__version__} by baskiton')
        req.add_header('Connection', 'close')
        return req

    def udp(self) -> bytes:
        """
        using UDP Tracker Protocol
        BEP15: http://bittorrent.org/beps/bep_0015.html

        Common / Connect request
        Offset  Size            Name            Value
        === common ==================
        0       64-bit integer  connection_id
        8       32-bit integer  action          ? // 0: connect; 1: announce; 2: scrape
        12      32-bit integer  transaction_id
        =============================
        16
        """

        self.transaction_id = self._udp_get_transaction_id()

        return struct.pack(self._COMMON_REQ_FMT + self._REQ_FMT,
                           self.connection_id, self.ACTION, self.transaction_id,
                           *self.params.values())

    @staticmethod
    def _udp_get_transaction_id() -> int:
        return int.from_bytes(secrets.token_bytes(4), 'big', signed=False)


class ConnectRequest(_Request):
    _CONNECT_PROTOCOL_ID = 0x41727101980

    def __init__(self, url: urllib.parse.ParseResultBytes):
        super(ConnectRequest, self).__init__(url, self._CONNECT_PROTOCOL_ID, False)


class AnnounceRequest(_Request):
    """
    UDP Announce request
    Offset  Size    Name    Value
    === common ==================
    0       64-bit integer  connection_id
    8       32-bit integer  action          1 // announce
    12      32-bit integer  transaction_id
    =============================
    16(0)   20-byte string  info_hash
    36(20)  20-byte string  peer_id
    56(40)  64-bit integer  downloaded
    64(48)  64-bit integer  left
    72(56)  64-bit integer  uploaded
    80(64)  32-bit integer  event           0 // 0: none; 1: completed; 2: started; 3: stopped
    84(68)  32-bit integer  IP address      0 // default
    88(72)  32-bit integer  key
    92(76)  32-bit integer  num_want        -1 // default
    96(80)  16-bit integer  port
    98(82)
    """

    ACTION = _TPReqType.ANNOUNCE
    _REQ_FMT = '20s20sQQQIIiiH'
    _HTTP_ANNOUNCE_EVENT = {
        AnnounceEvent.NONE: '',
        AnnounceEvent.COMPLETED: 'completed',
        AnnounceEvent.STARTED: 'started',
        AnnounceEvent.STOPPED: 'stopped',
    }

    def __init__(self,
                 url: urllib.parse.ParseResultBytes,
                 info_hash: bytes,
                 peer_id: bytes,
                 downloaded: int,
                 left: int,
                 uploaded: int,
                 event: AnnounceEvent = AnnounceEvent.NONE,
                 key: int = -1,
                 numwant: int = -1,
                 ip=0,
                 port: int = 6881):
        super(AnnounceRequest, self).__init__(
            url,
            info_hash=info_hash,
            peer_id=peer_id,
            downloaded=downloaded,
            left=left,
            uploaded=uploaded,
            event=event,
            ip=ip,
            key=key,
            numwant=numwant,
            port=port
        )

    def http(self) -> urllib.request.Request:
        self.params.update(
            compact=1,
            event=self._HTTP_ANNOUNCE_EVENT[self.params['event']]
        )
        # TODO: check ip, key
        return super(AnnounceRequest, self).http()


class ScrapeRequest(_Request):
    # TODO
    pass


class _Response:
    ACTION = None
    RESP_LEN = 0

    @classmethod
    def from_bytes(cls, buf: bytes, start: int):
        pass


class ConnectResponse(_Response):
    """
    Connect response
    Offset      Size            Name            Value
    === common ======================================
    0           32-bit integer  action          0 // connect
    4           32-bit integer  transaction_id
    =================================================
    8(0)        64-bit integer  connection_id
    16(8)
    """

    ACTION = _TPReqType.CONNECT
    _RESP_FMT = '!Q'
    RESP_LEN = struct.calcsize(_RESP_FMT)

    def __init__(self, connection_id: int):
        self.connection_id = connection_id

    @classmethod
    def from_bytes(cls, buf: bytes, start: int):
        return cls(*struct.unpack_from(cls._RESP_FMT, buf, start))


class AnnounceResponse(_Response):
    """
    Offset          Size            Name            Value
    === common ==========================================
    0               32-bit integer  action          1 // announce
    4               32-bit integer  transaction_id
    =====================================================
    8(0)            32-bit integer  interval
    12(4)           32-bit integer  leechers
    16(8)           32-bit integer  seeders
    20(12) + 6 * n  32-bit integer  IP address
    24(16) + 6 * n  16-bit integer  TCP port
    20(12) + 6 * N
    """

    ACTION = _TPReqType.ANNOUNCE
    _RESP_FMT = '!III'
    RESP_LEN = struct.calcsize(_RESP_FMT)
    _PEER_FMT = '!IH'

    def __init__(self, interval: int, leechers: int, seeders: int, peers: List[torrent.Peer] = None):
        self.interval = interval
        self.leechers = leechers
        self.seeders = seeders
        self.peers = peers or []

    @classmethod
    def from_bytes(cls, buf: bytes, start: int):
        resp = cls(*struct.unpack_from(cls._RESP_FMT, buf, start))
        for ip, port in struct.iter_unpack(cls._PEER_FMT, buf[cls.RESP_LEN + start:]):
            resp.peers.append(torrent.Peer(ip, port))
        return resp


class ScrapeResponse(_Response):
    """
    Offset          Size            Name            Value
    === common ==========================================
    0               32-bit integer  action          2 // scrape
    4               32-bit integer  transaction_id
    =====================================================
    8(0) + 12 * n   32-bit integer  seeders
    12(4) + 12 * n  32-bit integer  completed
    16(8) + 12 * n  32-bit integer  leechers
    8(0) + 12 * N
    """

    MAX_TORRENTS = 74
    ACTION = _TPReqType.SCRAPE
    _RESP_FMT = '!III'
    _TRUE_RESP_LEN = struct.calcsize(_RESP_FMT)
    FILE_NT = nt('file', 'seeders completed leechers name', defaults=[b''])

    def __init__(self, files: List[FILE_NT] = None):
        self.files = files or []

    @classmethod
    def from_bytes(cls, buf: bytes, start: int):
        return cls([cls.FILE_NT(*f)
                    for f in struct.iter_unpack(cls._RESP_FMT, buf[start:])])


class ErrorResponse(_Response, ConnectionError):
    """
    Offset      Size            Name            Value
    === common ======================================
    0           32-bit integer  action          3 // error
    4           32-bit integer  transaction_id
    =================================================
    8(0)        string  message
    """

    ACTION = _TPReqType.ERROR

    @classmethod
    def from_bytes(cls, buf: bytes, start: int):
        return cls(buf[start:].rstrip(b'\0').decode('ascii'))


class TrackerTransport:
    _CONNECTION_ID_TIMEOUT = 60
    _COMMON_RESP_FMT = '!II'
    _COMMON_RESP_LEN = struct.calcsize(_COMMON_RESP_FMT)
    _RESP_ACTIONS_MATCH = {
        _TPReqType.CONNECT: ConnectResponse,
        _TPReqType.ANNOUNCE: AnnounceResponse,
        _TPReqType.SCRAPE: ScrapeResponse,
        _TPReqType.ERROR: ErrorResponse,
    }

    def __init__(self, tracker_addr: bytes, proxies: Dict[str, str] = None):
        self.tracker_addr = urllib.parse.urlparse(tracker_addr)
        self.proxies = proxies
        self._proxy_handler = urllib.request.ProxyHandler(proxies)

        self.__connection_id = None
        self.__connection_id_start = 0
        self.__udp_ip = ''
        self.__udp_port = self.tracker_addr.port

    def add_proxie(self, proxies: Dict[str, str]):
        self.proxies.update(proxies)
        self._proxy_handler.__init__(self.proxies)

    def announce(self,
                 info_hash: bytes,
                 peer_id: bytes,
                 downloaded: int,
                 left: int,
                 uploaded: int,
                 event: AnnounceEvent = AnnounceEvent.NONE,
                 key: int = -1,
                 numwant: int = -1,
                 ip=0,
                 port: int = 6881):
        params = {
            'info_hash': info_hash,
            'peer_id': peer_id,
            'downloaded': downloaded,
            'left': left,
            'uploaded': uploaded,
            'event': event,
            'ip': ip,
            'key': key,
            'numwant': numwant,
            'port': port,
        }
        if self.tracker_addr.scheme in (b'http', b'https'):
            return self._http_announce(params)

        elif self.tracker_addr.scheme == b'udp':
            return self._udp_announce(params)

        raise ValueError(f'Unsupported url scheme: {self.tracker_addr.decode()}')

    def _http_send_request(self, req: _Request) -> Optional[Dict]:
        """
        using HTTP GET
        BEP3: http://bittorrent.org/beps/bep_0003.html
        """

        hdlr = urllib.request.ProxyHandler(self.proxies)
        opener = urllib.request.build_opener(self._proxy_handler)
        with opener.open(req.http()) as r:
            r: http.client.HTTPResponse
            response = r.read()
        try:
            result = bencode.decode_from_buffer(response)
        except (ValueError, TypeError, EOFError) as e:
            raise e(f'{e}: {response}')

        failure = result.get(b'failure reason')
        if failure:
            raise ErrorResponse(failure.decode('ascii'))
        return result

    def _http_announce(self, params: dict) -> Optional[AnnounceResponse]:
        resp = self._http_send_request(AnnounceRequest(self.tracker_addr, **params))

        intv = resp.get(b'min interval')
        if not intv:
            intv = resp[b'interval']
        result = AnnounceResponse(intv, resp.get(b'incomplete'), resp.get(b'complete'))

        peers = resp.get(b'peers')
        if isinstance(peers, bytes):
            # compact model
            result.peers = list(torrent.Peer(ip, port)
                                for ip, port in struct.iter_unpack('!IH', peers))
        elif isinstance(peers, list):
            # dictionary model
            result.peers = list(torrent.Peer(peer[b'ip'], peer[b'port'], peer.get(b'peer id'))
                                for peer in peers)

        return result

    def _udp_send_request(self, req: _Request) -> Optional[_Response]:
        """
        using UDP Tracker Protocol
        BEP15: http://bittorrent.org/beps/bep_0015.html
        """
        # TODO: log it

        t_ = 0
        with sk.socket(sk.AF_INET, sk.SOCK_DGRAM, sk.IPPROTO_UDP) as sock:
            for i in range(9):
                t = 15 * 2 ** i
                sock.settimeout(t)

                if req.dynamic_cid:
                    req.connection_id = self._udp_get_connection_id()

                print(f'send {req.ACTION.name} t={t_}')
                t_ += t

                sock.sendto(req.udp(), (self.__udp_ip, self.__udp_port))
                try:
                    resp = self._udp_build_response(sock.recv(8192), req.transaction_id)
                    if isinstance(resp, ErrorResponse):
                        raise resp
                    if resp.ACTION == req.ACTION:
                        return resp
                except sk.timeout:
                    # TODO: log it?
                    pass

    @classmethod
    def _udp_build_response(cls, buf: bytes, transaction_id: int):
        if len(buf) >= cls._COMMON_RESP_LEN:
            action, t_id = struct.unpack_from(cls._COMMON_RESP_FMT, buf)
            if t_id == transaction_id:
                resp_type = cls._RESP_ACTIONS_MATCH[_TPReqType(action)]
                if len(buf) >= resp_type.RESP_LEN + cls._COMMON_RESP_LEN:
                    return cls._RESP_ACTIONS_MATCH[_TPReqType(action)].from_bytes(buf, cls._COMMON_RESP_LEN)

    def _udp_connect(self) -> Optional[int]:
        self.__udp_ip = sk.gethostbyname(self.tracker_addr.hostname)
        print(f'connecting with {self.__udp_ip}')
        resp = self._udp_send_request(ConnectRequest(self.tracker_addr))

        if isinstance(resp, ConnectResponse):
            return resp.connection_id

    def _udp_get_connection_id(self) -> int:
        now = time.time()
        if (now - self.__connection_id_start > self._CONNECTION_ID_TIMEOUT
                or self.__connection_id is None):
            self.__connection_id = self._udp_connect()
            if self.__connection_id is not None:
                self.__connection_id_start = now
        return self.__connection_id

    def _udp_announce(self, params: dict) -> Optional[AnnounceResponse]:
        resp = self._udp_send_request(AnnounceRequest(self.tracker_addr, **params))

        if isinstance(resp, AnnounceResponse):
            return resp
