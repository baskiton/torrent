__all__ = (
    'Response', 'AnnounceResponse', 'ErrorResponse', 'ScrapeResponse',
    'Request', 'AnnounceRequest', 'ScrapeRequest',
    'AnnounceEvent'
)

import enum
import errno
import http.client
import io
import multiprocessing as mp
import multiprocessing.connection as mpcon
import secrets
import select
import socket as sk
import struct
import threading
import urllib.parse
import urllib.request
import urllib.response

from collections import namedtuple as nt
from typing import AnyStr, List, Optional, Sequence, Set, Tuple

import btorrent


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


class Request:
    ACTION = _TPReqType.CONNECT
    _COMMON_REQ_FMT = '!QII'
    _REQ_FMT = ''

    def __init__(self,
                 url: urllib.parse.ParseResultBytes,
                 connection_id: int = None,
                 **params) -> None:
        self.url = url
        self.connection_id = connection_id
        self.transaction_id = None
        self.params = params

    def get_req(self) -> urllib.request.Request:
        if self.url.scheme == b'udp':
            return urllib.request.Request(self.url.geturl().decode('idna'), self)
        if self.url.scheme.startswith(b'http'):
            return self.http()

    def http(self) -> urllib.request.Request:
        """
        using HTTP GET
        BEP3: http://bittorrent.org/beps/bep_0003.html
        """

        req = urllib.request.Request(f'{self.url.geturl().decode("idna")}'
                                     f'{self.url.query and "&" or "?"}'
                                     f'{urllib.parse.urlencode(self.params, True)}',
                                     method='GET')
        req.add_header('User-agent', f'pyTorrent/{btorrent.__version__} by baskiton')
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

        params = self.params.values()
        if len(params) == 1:
            params, = params
            req_cnt = len(params)
        else:
            req_cnt = 1

        return struct.pack(self._COMMON_REQ_FMT + self._REQ_FMT * req_cnt,
                           self.connection_id, self.ACTION, self.transaction_id,
                           *params)

    @staticmethod
    def _udp_get_transaction_id() -> int:
        return int.from_bytes(secrets.token_bytes(4), 'big', signed=False)


class ConnectRequest(Request):
    _CONNECT_PROTOCOL_ID = 0x41727101980

    def __init__(self, url: urllib.parse.ParseResultBytes) -> None:
        super(ConnectRequest, self).__init__(url, self._CONNECT_PROTOCOL_ID)


class AnnounceRequest(Request):
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
                 port: int = 6881) -> None:
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


class ScrapeRequest(Request):
    """
    UDP Scrape request
    Offset          Size            Name            Value
    === common ==================
    0               64-bit integer  connection_id
    8               32-bit integer  action          2 // scrape
    12              32-bit integer  transaction_id
    === common ==================
    16 + 20 * n     20-byte string  info_hash
    16 + 20 * N
    """
    ACTION = _TPReqType.SCRAPE
    _REQ_FMT = '20s'

    def __init__(self, url: urllib.parse.ParseResultBytes, info_hash: Sequence[bytes] = ()) -> None:
        u = list(url)
        if u[2].endswith(b'/announce'):
            u[2] = u[2][:-9] + b'/scrape'
        else:
            raise ValueError(f'Scrape not supported by tracker {url.hostname.decode()}')
        url = urllib.parse.ParseResultBytes(*u)

        super(ScrapeRequest, self).__init__(url, info_hash=info_hash)


class Response:
    ACTION = None
    _RESP_LEN = 0
    _COMMON_RESP_FMT = '!II'
    _COMMON_RESP_LEN = struct.calcsize(_COMMON_RESP_FMT)

    @classmethod
    def from_buf(cls, buf: io.BytesIO) -> Optional['Response']:
        pass

    @classmethod
    def from_bencode(cls, buf: bytes) -> Optional['Response']:
        pass

    @classmethod
    def build(cls, resp: bytes, transaction_id=0) -> Optional['Response']:
        """
        Connect response
        Offset      Size            Name            Value
        === common ======================================
        0           32-bit integer  action          0 // connect
        4           32-bit integer  transaction_id
        =================================================
        8(0)
        """
        try:
            resp = btorrent.bencode.decode_from_buffer(resp)
        except (ValueError, TypeError, EOFError):
            if len(resp) >= cls._COMMON_RESP_LEN:
                buf = io.BytesIO(resp)
                action, t_id = struct.unpack(cls._COMMON_RESP_FMT, buf.read(cls._COMMON_RESP_LEN))
                if t_id == transaction_id:
                    return _RESP_ACTIONS_MATCH[_TPReqType(action)].from_buf(buf)
        else:
            failure = resp.get(b'failure reason')
            if failure:
                return ErrorResponse(failure.decode('ascii'))

            return (ScrapeResponse if b'files' in resp else AnnounceResponse).from_bencode(resp)


class ConnectResponse(Response):
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
    _RESP_LEN = struct.calcsize(_RESP_FMT)

    def __init__(self, connection_id: int):
        self.connection_id = connection_id

    @classmethod
    def from_buf(cls, buf: io.BytesIO) -> Optional['ConnectResponse']:
        x = buf.read(cls._RESP_LEN)
        if len(x) == cls._RESP_LEN:
            return cls(*struct.unpack(cls._RESP_FMT, x))


class AnnounceResponse(Response):
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
    _RESP_LEN = struct.calcsize(_RESP_FMT)
    _PEER_FMT = '!IH'

    def __init__(self, interval: int, leechers: int, seeders: int, peers: List[btorrent.Peer] = None) -> None:
        self.interval = interval
        self.leechers = leechers
        self.seeders = seeders
        self.peers: List[btorrent.Peer] = peers or []
        self.tracker_id = b''

    @classmethod
    def from_buf(cls, buf: io.BytesIO) -> Optional['AnnounceResponse']:
        x = buf.read(cls._RESP_LEN)
        if len(x) >= cls._RESP_LEN:
            resp = cls(*struct.unpack(cls._RESP_FMT, x))
            for ip, port in struct.iter_unpack(cls._PEER_FMT, buf.read()):
                resp.peers.append(btorrent.Peer(ip, port))
            return resp

    @classmethod
    def from_bencode(cls, data: dict) -> Optional['AnnounceResponse']:
        resp = cls(0, 0, 0)
        resp.interval = data.get(b'min interval') or data[b'interval']
        resp.leechers = data.get(b'incomplete', 0)
        resp.seeders = data.get(b'complete', 0)
        resp.tracker_id = data.get(b'tracker id', b'')

        peers = data.get(b'peers')
        if isinstance(peers, bytes):
            # compact model
            resp.peers = list(btorrent.Peer(ip, port)
                              for ip, port in struct.iter_unpack('!IH', peers))
        elif isinstance(peers, list):
            # dictionary model
            resp.peers = list(btorrent.Peer(peer[b'ip'], peer[b'port'], peer.get(b'peer id'))
                              for peer in peers)

        return resp


class ScrapeResponse(Response):
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
    _RESP_FMT = ''
    _FILE_FMT = '!III'
    FILE_NT = nt('file', 'seeders completed leechers name info_hash', defaults=[b'', b''])

    def __init__(self, files: List[FILE_NT] = None) -> None:
        self.files = files or []

    @classmethod
    def from_buf(cls, buf: io.BytesIO) -> Optional['ScrapeResponse']:
        return cls([cls.FILE_NT(*f)
                    for f in struct.iter_unpack(cls._FILE_FMT, buf.read())])

    @classmethod
    def from_bencode(cls, data: dict) -> Optional['ScrapeResponse']:
        return cls(
            [cls.FILE_NT(file[b'complete'], file[b'downloaded'], file[b'incomplete'], file.get(b'name', b''), info_hash)
             for info_hash, file in data[b'files'].items()]
        )


class ErrorResponse(Response, ConnectionError):
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
    def from_buf(cls, buf: io.BytesIO) -> Optional['ErrorResponse']:
        x = buf.read()
        if x:
            return cls(x.rstrip(b'\0').decode('ascii'))


_RESP_ACTIONS_MATCH = {
    _TPReqType.CONNECT: ConnectResponse,
    _TPReqType.ANNOUNCE: AnnounceResponse,
    _TPReqType.SCRAPE: ScrapeResponse,
    _TPReqType.ERROR: ErrorResponse,
}


class UDPConnection:
    def __init__(self, req: urllib.request.Request) -> None:
        u = urllib.parse.urlsplit(req.full_url)
        if req.has_proxy():
            self.peer_addr = urllib.parse._splitnport(req.host, 80)
        else:
            self.peer_addr: Tuple[AnyStr, int] = (u.hostname, u.port)

        self.sock: Optional[sk.socket] = None
        self.connection_id: Optional[int] = None

        self.__header = b''
        self.__response: Optional[Response] = None

    def connect(self) -> None:
        print(f'try connecting with {self.peer_addr}')

        main_con, child_con = mp.Pipe(True)

        ths = {}
        for addr_info in sk.getaddrinfo(*self.peer_addr, 0, sk.SOCK_DGRAM, sk.IPPROTO_UDP):
            t = threading.Thread(target=self._connect, args=(child_con, addr_info), daemon=True)
            t.start()
            ths[t.ident] = t

        while ths:
            x = main_con.recv()
            if isinstance(x, int):
                ths.pop(x, None)
                continue
            thr_id, sock, resp = x
            sock: sk.socket
            resp: Response

            if not resp:
                sock.close()
                ths.pop(thr_id, None)
                continue

            self.sock = sock
            self.connection_id = resp.connection_id
            break

        main_con.send('.')
        for t in ths.values():
            t.join()

        if not self.sock:
            raise ConnectionError(errno.EHOSTUNREACH, f'Tracker {self.peer_addr} is unreachable')

        print('OK')

    def _connect(self, con: mpcon.Connection, addr_info: Tuple) -> None:
        af, socktype, proto, canonname, sa = addr_info
        con_req = ConnectRequest(urllib.parse.urlparse(
            f'udp://{self.peer_addr[0]}:{self.peer_addr[1]}'.encode('idna')))
        poller = select.poll()
        sock = sk.socket(af, socktype, proto)

        poller.register(sock.fileno(), select.POLLIN)
        poller.register(con.fileno(), select.POLLIN)

        sock.connect(sa)
        for i in range(9):
            t = 15000 * 2 ** i  # ms
            sock.sendall(self.__header + con_req.udp())

            for fd, evt in poller.poll(t):
                if fd == sock.fileno():
                    x = sock.recv(65535)
                    resp = Response.build(x, con_req.transaction_id)
                    if (not resp
                            or (resp.ACTION != con_req.ACTION
                                and not isinstance(resp, ErrorResponse))):
                        break
                    if isinstance(resp, ErrorResponse):
                        raise resp
                    con.send((threading.get_ident(), sock, resp))
                else:
                    sock.close()
                return

    def close(self) -> None:
        try:
            s = self.sock
            if s:
                self.sock = None
                s.close()
        finally:
            self.__response = None

    def send_request(self, req: Request) -> Optional[Response]:
        if self.sock is None:
            self.connect()

        if self.connection_id is not None:
            req.connection_id = self.connection_id

        self.__response = self._send_request(self.sock, req)
        return self.__response

    def _send_request(self, con: sk.socket, req: Request) -> Optional[Response]:
        print(f'send {req.ACTION.name} t=0')
        for i in range(9):
            t = 15 * 2 ** i
            con.settimeout(t)

            con.sendall(self.__header + req.udp())
            try:
                resp = con.recv(65535)
            except sk.timeout:
                print(f'send {req.ACTION.name} {t=}')
                # TODO: log it?
                continue

            resp = Response.build(resp, req.transaction_id)
            if (not resp
                    or (resp.ACTION != req.ACTION
                        and not isinstance(resp, ErrorResponse))):
                continue
            return resp
        raise ConnectionError(errno.EHOSTUNREACH, f'Tracker {self.peer_addr} is unreachable')

    def get_response(self) -> Response:
        return self.__response

    def read(self) -> Response:
        return self.__response

    def set_socks5_header(self, header: bytes) -> None:
        self.__header = header


class UDPHandler(urllib.request.BaseHandler):

    def udp_open(self, req: urllib.request.Request) -> UDPConnection:
        print('udp_open', req.full_url)
        con = UDPConnection(req)
        con.connect()
        con.send_request(req.data)
        return con


class TrackerOpener(urllib.request.OpenerDirector):
    def open(self, fullurl, data=None, timeout=sk._GLOBAL_DEFAULT_TIMEOUT) -> Response:
        x = super(TrackerOpener, self).open(fullurl, data, timeout).read()
        if isinstance(x, bytes):
            return Response.build(x)
        return x


def build_opener(*handlers) -> TrackerOpener:
    opener = TrackerOpener()
    default_classes = [urllib.request.ProxyHandler, urllib.request.UnknownHandler, urllib.request.HTTPHandler,
                       urllib.request.HTTPDefaultErrorHandler, urllib.request.HTTPRedirectHandler,
                       urllib.request.FTPHandler, urllib.request.FileHandler, urllib.request.HTTPErrorProcessor,
                       urllib.request.DataHandler, UDPHandler]
    if hasattr(http.client, "HTTPSConnection"):
        default_classes.append(urllib.request.HTTPSHandler)
    skip = set()
    for klass in default_classes:
        for check in handlers:
            if isinstance(check, type):
                if issubclass(check, klass):
                    skip.add(klass)
            elif isinstance(check, klass):
                skip.add(klass)
    for klass in skip:
        default_classes.remove(klass)

    for klass in default_classes:
        opener.add_handler(klass())

    for h in handlers:
        if isinstance(h, type):
            h = h()
        opener.add_handler(h)
    return opener
