__all__ = 'HTTPTrackerTransport', 'UDPTrackerTransport'

import enum
import http.client
import random
import secrets
import socket as sk
import struct
import time
import urllib.parse
import urllib.request

from collections import namedtuple
from typing import Any, AnyStr, List, Tuple, Union

from torrent import __version__, bencode


class TPReqType(enum.IntEnum):
    CONNECT = 0
    ANNOUNCE = 1
    SCRAPE = 2
    ERROR = 3


@enum.unique
class TPEvent(enum.IntEnum):
    NONE = 0
    COMPLETED = 1
    STARTED = 2
    STOPPED = 3


_ANNOUNCE_REQ_FMT = '!QII20s20sQQQIIIIH'
_ANNOUNCE_REQ_NT = namedtuple(
    'announce_req',
    ['connection_id', 'action', 'transaction_id', 'info_hash', 'peer_id', 'downloaded',
     'left', 'uploaded', 'event', 'IP', 'key', 'numwant', 'port'],
    defaults=[0, TPReqType.ANNOUNCE, 0, 0, 0, 0, 0, 0, TPEvent.NONE, 0, 0, -1, 0]
)


class TrackerTransport:
    def __init__(self, tracker_addr: bytes):
        self.tracker_addr = urllib.parse.urlparse(tracker_addr)
        if self.tracker_addr.scheme in (b'http', b'https'):
            self.__send_request = self._http_send_request
        elif self.tracker_addr.scheme == b'udp':
            self.__send_request = self._udp_send_request

        self.__connection_id = None
        self.__connection_id_start = 0

    def announce(self,
                 info_hash,
                 peer_id,
                 downloaded,
                 left,
                 uploaded,
                 event,
                 ip,
                 key,
                 numwant,
                 port,
                 compact):
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
            'compact': compact,
        }
        if self.tracker_addr.scheme in (b'http', b'https'):
            return self._http_send_request(params)
        elif self.tracker_addr.scheme == b'udp':
            params['connection_id'] = self._udp_get_connection_id()
            params['action'] = self._ACTION_ANNOUNCE
            params['transaction_id'] = self._udp_get_transaction_id()
            return self._udp_announce(params)

    def _http_send_request(self, params: dict) -> bytes:
        req = urllib.request.Request(f'{self.tracker_addr.geturl()}'
                                     f'{self.tracker_addr.query and "&" or "?"}'
                                     f'{urllib.parse.urlencode(params)}',
                                     method='GET')
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

    def _udp_announce(self, params: dict):
        pass

    def _udp_send_request(self, req: bytes) -> bytes:
        t = 0
        with sk.socket(sk.AF_INET, sk.SOCK_DGRAM, sk.IPPROTO_UDP) as sock:
            sock.connect(self.tracker_addr)
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

    @staticmethod
    def _udp_get_transaction_id():
        return int.from_bytes(secrets.token_bytes(4), 'big', signed=False)

    def _udp_connect(self) -> int:
        """
        Offset  Size            Name            Value
        0       64-bit integer  protocol_id     0x41727101980 // magic constant
        8       32-bit integer  action          0 // connect
        12      32-bit integer  transaction_id
        16
        """

        transaction_id = self._udp_get_transaction_id()
        req = struct.pack(self._CONNECT_REQ_FMT,
                          self._CONNECT_PROTOCOL_ID,
                          self._ACTION_CONNECT,
                          transaction_id)
        resp = self._send_request(req)
        if len(resp) >= self._CONNECT_RESP_LEN:
            action, t_id, con_id = struct.unpack(self._CONNECT_RESP_FMT, resp)
            if t_id == transaction_id and action == self._ACTION_CONNECT:
                return con_id

    def _udp_get_connection_id(self):
        now = time.time()
        if (now - self.__connection_id_start > self._CONNECTION_ID_TIMEOUT
                or self.__connection_id is None):
            self.__connection_id = self._udp_connect()
            if self.__connection_id is not None:
                self.__connection_id_start = now
        return self.__connection_id


class _TrackerTransport:
    _ACTION_CONNECT = 0
    ACTION_ANNOUNCE = 1
    ACTION_SCRAPE = 2
    _ACTION_ERROR = 3

    _HTTP_EVT = {
        TPEvent.NONE: '',
        TPEvent.COMPLETED: 'completed',
        TPEvent.STARTED: 'started',
        TPEvent.STOPPED: 'stopped',
    }

    _CONNECTION_ID_TIMEOUT = 60
    _CONNECT_REQ_FMT = '!QII'
    _CONNECT_PROTOCOL_ID = 0x41727101980
    _CONNECT_RESP_FMT = '!IIQ'
    _CONNECT_RESP_LEN = struct.calcsize(_CONNECT_RESP_FMT)

    _ANNOUNCE_REQ_FMT = '!QII20s20sQQQIIIIH'

    def __init__(self, tracker_addr: Union[AnyStr, List[List[bytes]]]):
        if isinstance(tracker_addr, (str, bytes)):
            if isinstance(tracker_addr, str):
                tracker_addr = tracker_addr.encode('utf8')
            tracker_addr = [[tracker_addr]]
        self.tracker_addr: List[List[bytes]] = tracker_addr

        # shuffle urls in levels for first read
        # by BEP12: http://bittorrent.org/beps/bep_0012.html
        for lvl in self.tracker_addr:
            random.shuffle(lvl)

        self.__connection_id = None
        self.__connection_id_start = 0

    def announce(self,
                 info_hash,
                 peer_id,
                 downloaded,
                 left,
                 uploaded,
                 event,
                 ip,
                 key,
                 numwant,
                 port,
                 compact):
        req = {
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
            'compact': compact,
        }

    @staticmethod
    def _get_transaction_id():
        return int.from_bytes(secrets.token_bytes(4), 'big', signed=False)

    def _get_connection_id(self):
        now = time.time()
        if (now - self.__connection_id_start > self._CONNECTION_ID_TIMEOUT
                or self.__connection_id is None):
            self.__connection_id = self._connect()
            if self.__connection_id is not None:
                self.__connection_id_start = now
        return self.__connection_id

    def send_request(self, req_type: TPReqType, params: dict):
        for lvl in self.tracker_addr:
            for idx, url in enumerate(lvl):
                result = self._send_request(url, req_type, params)
                if result:
                    lvl.pop(idx)
                    lvl.insert(0, url)
                    self.last_connecting_time = time.time()
                    return result

    def _send_request(self, url: bytes, req_type: TPReqType, params: dict):
        u = urllib.parse.urlparse(url)
        if u.scheme == 'udp':
            #TODO:
            # using UDP Tracker Protocol
            # BEP15: http://bittorrent.org/beps/bep_0015.html
            return transport.tracker.udp_request(u)

        elif u.scheme in ('http', 'https'):
            # using HTTP GET
            # BEP3: http://bittorrent.org/beps/bep_0003.html
            requests_keys = {
                'info_hash': self.torrent.info_hash,
                'peer_id': self.peer_id,
                'downloaded': self.torrent.downloaded,
                'left': self.torrent.left,
                'uploaded': self.torrent.uploaded,
                'event': event,
                # 'ip': ,
                # 'key': ,
                'numwant': self.numwant,
                'port': self.port,
                'compact': 1,
            }
            return transport.tracker.http_request(u, requests_keys)

        raise ValueError(f'Unsupported url scheme: {u.geturl()}')


class HTTPTrackerTransport(_TrackerTransport):
    _EVT_DICT = {
        TPEvent.NONE: '',
        TPEvent.COMPLETED: 'completed',
        TPEvent.STARTED: 'started',
        TPEvent.STOPPED: 'stopped',
    }

    # def __init__(self,
    #              tracker_addr: urllib.parse.ParseResult,
    #              info_hash: bytes,
    #              peer_id: bytes,
    #              key: int = 0,
    #              num_want: int = -1,
    #              ip=0,
    #              port: int = 6881):
    #     super().__init__(tracker_addr, info_hash, peer_id, key or '', num_want, ip or '', port)

    def send_request(self, tracker_addr: urllib.parse.ParseResult, params: dict) -> bytes:
        req = urllib.request.Request(f'{tracker_addr.geturl()}'
                                     f'{tracker_addr.query and "&" or "?"}'
                                     f'{urllib.parse.urlencode(params)}',
                                     method='GET')
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

    def announce(self, downloaded: int, left: int, uploaded: int, event: TPEvent = TPEvent.NONE):
        # BEP3: https://www.bittorrent.org/beps/bep_0003.html

        return self._send_request({
            'info_hash': self.info_hash,
            'peer_id': self.peer_id,
            'downloaded': downloaded,
            'left': left,
            'uploaded': uploaded,
            'event': self._EVT_DICT[event],
            'ip': self.ip,
            'key': self.key,
            'numwant': self.num_want,
            'port': self.port,
            'compact': 1,
        })


class UDPTrackerTransport(_TrackerTransport):
    """
    UDP Tracker Protocol for BitTorrent
    # BEP15: https://www.bittorrent.org/beps/bep_0015.html
    """
    ACTION_CONNECT = 0
    ACTION_ANNOUNCE = 1
    ACTION_SCRAPE = 2
    ACTION_ERROR = 3

    _CONNECTION_ID_TIMEOUT = 60
    _CONNECT_REQ_FMT = '!QII'
    _CONNECT_PROTOCOL_ID = 0x41727101980
    _CONNECT_RESP_FMT = '!IIQ'
    _CONNECT_RESP_LEN = struct.calcsize(_CONNECT_RESP_FMT)

    _ANNOUNCE_REQ_FMT = '!QII20s20sQQQIIIIH'

    def __init__(self,
                 tracker_addr: Tuple[Any, int],
                 info_hash: bytes,
                 peer_id: bytes,
                 key: int = 0,
                 num_want: int = -1,
                 ip=0,
                 port: int = 6881):
        super().__init__(tracker_addr, info_hash, peer_id, key, num_want, ip, port)
        self.__connection_id = None
        self.__connection_id_start = 0

    def _send_request(self, req: bytes) -> bytes:
        t = 0
        with sk.socket(sk.AF_INET, sk.SOCK_DGRAM, sk.IPPROTO_UDP) as sock:
            sock.connect(self.tracker_addr)
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

    @staticmethod
    def _get_transaction_id():
        return int.from_bytes(secrets.token_bytes(4), 'big', signed=False)

    def _get_connection_id(self):
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

        transaction_id = self._get_transaction_id()
        req = struct.pack(self._CONNECT_REQ_FMT,
                          self._CONNECT_PROTOCOL_ID,
                          self._ACTION_CONNECT,
                          transaction_id)
        resp = self._send_request(req)
        if len(resp) >= self._CONNECT_RESP_LEN:
            action, t_id, con_id = struct.unpack(self._CONNECT_RESP_FMT, resp)
            if t_id == transaction_id and action == self._ACTION_CONNECT:
                return con_id

    def announce(self, downloaded: int, left: int, uploaded: int, event: TPEvent = TPEvent.NONE):
        """
        Offset  Size    Name    Value
        0       64-bit integer  connection_id
        8       32-bit integer  action          1 // announce
        12      32-bit integer  transaction_id
        16      20-byte string  info_hash
        36      20-byte string  peer_id
        56      64-bit integer  downloaded
        64      64-bit integer  left
        72      64-bit integer  uploaded
        80      32-bit integer  event           0 // 0: none; 1: completed; 2: started; 3: stopped
        84      32-bit integer  IP address      0 // default
        88      32-bit integer  key
        92      32-bit integer  num_want        -1 // default
        96      16-bit integer  port
        98
        """

        transaction_id = self._get_transaction_id()
        req = struct.pack(
            self._ANNOUNCE_REQ_FMT,
            self._get_connection_id(),
            self._ACTION_ANNOUNCE,
            transaction_id,
            self.info_hash,
            self.peer_id,
            downloaded,
            left,
            uploaded,
            event,
            self.ip,
            self.key,
            self.num_want,
            self.port
        )
