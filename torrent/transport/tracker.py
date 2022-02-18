__all__ = 'AnnounceEvent', 'AnnounceResponse', 'TrackerTransport'

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


_HTTP_ANNOUNCE_EVENT = {
    AnnounceEvent.NONE: '',
    AnnounceEvent.COMPLETED: 'completed',
    AnnounceEvent.STARTED: 'started',
    AnnounceEvent.STOPPED: 'stopped',
}


@enum.unique
class _TPReqType(enum.IntEnum):
    CONNECT = 0
    ANNOUNCE = 1
    SCRAPE = 2
    ERROR = 3


# Connect request
# Offset  Size            Name            Value
# 0       64-bit integer  protocol_id     0x41727101980 // magic constant
# 8       32-bit integer  action          0 // connect
# 12      32-bit integer  transaction_id
# 16
_CONNECTION_ID_TIMEOUT = 60
_CONNECT_PROTOCOL_ID = 0x41727101980
_CONNECT_REQ_FMT = '!QII'
_CONNECT_REQ_NT = nt(
    'connect_req',
    'protocol_id action transaction_id',
    defaults=[_CONNECT_PROTOCOL_ID, _TPReqType.CONNECT, None]
)

# Connect response
# Offset  Size            Name            Value
# 0       32-bit integer  action          0 // connect
# 4       32-bit integer  transaction_id
# 8       64-bit integer  connection_id
# 16
_CONNECT_RESP_FMT = '!IIQ'
_CONNECT_RESP_NT = nt('connect_req', 'action transaction_id connection_id')
_CONNECT_RESP_LEN = struct.calcsize(_CONNECT_RESP_FMT)

# Announce request
# Offset  Size    Name    Value
# 0       64-bit integer  connection_id
# 8       32-bit integer  action          1 // announce
# 12      32-bit integer  transaction_id
# 16      20-byte string  info_hash
# 36      20-byte string  peer_id
# 56      64-bit integer  downloaded
# 64      64-bit integer  left
# 72      64-bit integer  uploaded
# 80      32-bit integer  event           0 // 0: none; 1: completed; 2: started; 3: stopped
# 84      32-bit integer  IP address      0 // default
# 88      32-bit integer  key
# 92      32-bit integer  num_want        -1 // default
# 96      16-bit integer  port
# 98
_ANNOUNCE_REQ_FMT = '!QII20s20sQQQIIiiH'
_ANNOUNCE_REQ_NT = nt(
    'announce_req',
    'connection_id action transaction_id info_hash peer_id '
    'downloaded left uploaded event ip key numwant port',
    defaults=[None, _TPReqType.ANNOUNCE, None, None, None,
              None, None, None, AnnounceEvent.NONE, 0, None, -1, None]
)

# Announce response
# Offset      Size            Name            Value
# 0           32-bit integer  action          1 // announce
# 4           32-bit integer  transaction_id
# 8           32-bit integer  interval
# 12          32-bit integer  leechers
# 16          32-bit integer  seeders
# 20 + 6 * n  32-bit integer  IP address
# 24 + 6 * n  16-bit integer  TCP port
# 20 + 6 * N
_ANNOUNCE_RESP_FMT = '!IIIII'
_ANNOUNCE_RESP_LEN = struct.calcsize(_ANNOUNCE_RESP_FMT)
_ANNOUNCE_RESP_NT = nt('announce_resp', 'action transaction_id interval leechers seeders')
_ANNOUNCE_PEER_FMT = '!IH'
_ANNOUNCE_PEER_NT = nt('peer', 'ip port')


class AnnounceResponse:
    def __init__(self, interval: int, leechers: int, seeders: int, peers: List[torrent.Peer] = None, **kw):
        self.interval = interval
        self.leechers = leechers
        self.seeders = seeders
        self.peers = peers or []


class TrackerTransport:
    def __init__(self, tracker_addr: bytes):
        self.tracker_addr = urllib.parse.urlparse(tracker_addr)

        self.__connection_id = None
        self.__connection_id_start = 0

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

    def _http_send_request(self, url: urllib.parse.ParseResultBytes, params: dict) -> Optional[Dict]:
        """
        using HTTP GET
        BEP3: http://bittorrent.org/beps/bep_0003.html
        """

        req = urllib.request.Request(f'{url.geturl().decode("ascii")}'
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

    def _http_announce(self, params: dict) -> Optional[AnnounceResponse]:
        params['compact'] = 1
        params['event'] = _HTTP_ANNOUNCE_EVENT[params['event']]
        # TODO: check ip, key

        resp = self._http_send_request(self.tracker_addr, params)

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

    def _udp_send_request(self, resp_fmt: str, resp_nt: Union[NamedTuple, nt], **params) -> Tuple[bytes, int]:
        """
        using UDP Tracker Protocol
        BEP15: http://bittorrent.org/beps/bep_0015.html
        """
        # TODO: log it

        transaction_id = 0
        resp = b''
        t_ = 0
        with sk.socket(sk.AF_INET, sk.SOCK_DGRAM, sk.IPPROTO_UDP) as sock:
            sock.connect((self.tracker_addr.hostname, self.tracker_addr.port))
            print(f'send to {self.tracker_addr.geturl().decode("ascii")}')
            for i in range(9):
                if 'connection_id' in params:
                    params['connection_id'] = self._udp_get_connection_id()
                transaction_id = self._udp_get_transaction_id()
                x = resp_nt(transaction_id=transaction_id, **params)
                print(x)
                req = struct.pack(resp_fmt, *x)

                print(f'send t={t_}')
                t = 15 * 2 ** i
                t_ += t
                sock.settimeout(t)

                sock.send(req)
                try:
                    resp = sock.recv(8192)
                    break
                except sk.timeout:
                    # TODO: log it?
                    pass

        if len(resp) >= 8:
            action, t_id = struct.unpack_from('!II', resp)
            if action == _TPReqType.ERROR:
                if t_id == transaction_id:
                    raise ConnectionError(f'Tracker error: {resp[8:].decode()}')

        return resp, transaction_id

    @staticmethod
    def _udp_get_transaction_id() -> int:
        return int.from_bytes(secrets.token_bytes(4), 'big', signed=False)

    def _udp_connect(self) -> Optional[int]:
        resp, transaction_id = self._udp_send_request(_CONNECT_REQ_FMT, _CONNECT_REQ_NT)

        if len(resp) >= _CONNECT_RESP_LEN:
            resp = _CONNECT_RESP_NT._make(struct.unpack_from(_CONNECT_RESP_FMT, resp))
            if resp.transaction_id == transaction_id and resp.action == _TPReqType.CONNECT:
                return resp.connection_id

    def _udp_get_connection_id(self) -> int:
        now = time.time()
        if (now - self.__connection_id_start > _CONNECTION_ID_TIMEOUT
                or self.__connection_id is None):
            self.__connection_id = self._udp_connect()
            if self.__connection_id is not None:
                self.__connection_id_start = now
        return self.__connection_id

    def _udp_announce(self, params: dict) -> Optional[AnnounceResponse]:
        params.update(action=_TPReqType.ANNOUNCE, connection_id=0)
        resp, transaction_id = self._udp_send_request(_ANNOUNCE_REQ_FMT, _ANNOUNCE_REQ_NT, **params)

        if len(resp) >= _ANNOUNCE_RESP_LEN:
            res = _ANNOUNCE_RESP_NT._make(struct.unpack_from(_ANNOUNCE_RESP_FMT, resp))
            if (res.transaction_id == transaction_id
                    and res.action == _TPReqType.ANNOUNCE):
                result = AnnounceResponse(**res._asdict())
                for peer in struct.iter_unpack(_ANNOUNCE_PEER_FMT, resp[_ANNOUNCE_RESP_LEN:]):
                    result.peers.append(torrent.Peer(**_ANNOUNCE_PEER_NT._make(peer)._asdict()))
                return result
