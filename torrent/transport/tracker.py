import enum
import http.client
import secrets
import socket as sk
import time
import urllib.parse
import urllib.request
import struct

from torrent import __version__, bencode


def http_request(url: urllib.parse.ParseResult, params: dict = None, headers: dict = None):
    # BEP3: https://www.bittorrent.org/beps/bep_0003.html

    query = urllib.parse.urlencode(params or {})
    req = urllib.request.Request(f'{url.geturl()}{url.query and "&" or "?"}{query}',
                                 method='GET', headers=headers or {})
    req.add_header('User-agent', f'pyTorrent/{__version__} by baskiton')
    with urllib.request.urlopen(req) as r:
        r: http.client.HTTPResponse
        response = r.read()
    try:
        result = bencode.decode_from_buffer(response)
    except (ValueError, TypeError, EOFError) as e:
        raise ValueError(f'{e}: {response}')
    failure = result.get(b'failure reason')
    if failure:
        raise ValueError(failure.decode())
    return result


@enum.unique
class _UDPTPAction(enum.IntEnum):
    CONNECT = 0
    ANNOUNCE = 1
    SCRAPE = 2
    ERROR = 3


class _UDPTrackerProtocol:
    _CONNECTION_ID_TIMEOUT = 60
    _CONNECT_REQ_FMT = '!QLL'
    _CONNECT_PROTOCOL_ID = 0x41727101980
    _CONNECT_RESP_FMT = '!LLQ'

    def __init__(self, ip, port: int):
        self.ip = ip
        self.port = port
        self.__connection_id = None
        self.__connection_id_start = 0

    @property
    def connection_id(self):
        now = time.time()
        if (now - self.__connection_id_start > self._CONNECTION_ID_TIMEOUT
                or self.__connection_id is None):
            self.__connection_id = self._connect()
            if self.__connection_id is not None:
                self.__connection_id_start = now
        return self.__connection_id

    def _connect(self) -> int:
        """
        Offset  Size            Name            Value
        0       64-bit integer  protocol_id     0x41727101980 // magic constant
        8       32-bit integer  action          0 // connect
        12      32-bit integer  transaction_id
        16
        """

        transaction_id = int.from_bytes(secrets.token_bytes(4), 'big', signed=False)
        req = struct.pack(self._CONNECT_REQ_FMT, self._CONNECT_PROTOCOL_ID, _UDPTPAction.CONNECT, transaction_id)
        resp = self._send_request(req)
        if len(resp) >= struct.calcsize(self._CONNECT_RESP_FMT):
            action, t_id, con_id = struct.unpack(self._CONNECT_RESP_FMT, resp)
            if t_id == transaction_id and action == _UDPTPAction.CONNECT:
                return con_id

    def announce(self):
        pass

    def scrape(self):
        pass

    def error(self):
        pass

    def _send_request(self, req: bytes) -> bytes:
        t = 0
        with sk.socket(sk.AF_INET, sk.SOCK_DGRAM, sk.IPPROTO_UDP) as sock:
            sock.connect((self.ip, self.port))
            for i in range(9):
                print(f'send {t=}')
                t = 15 * 2 ** i
                sock.settimeout(t)
                sock.send(req)
                try:
                    # for some unknown reason, it sometimes hangs on the first iteration.юю
                    resp = sock.recv(8192)
                    return resp
                except sk.timeout:
                    # TODO: log it?
                    pass
            return b''


def udp_request(url: urllib.parse.ParseResult):
    # BEP15: https://www.bittorrent.org/beps/bep_0015.html

    conn = _UDPTrackerProtocol(url.hostname, url.port or 17)
    print('connection_id', conn.connection_id)
    print('connection_id', conn.connection_id)
    return 1
