import enum
import io
import ipaddress
import re
import struct
import socket as sk

from typing import Optional, Tuple


class UTP:
    """
    uTorrent Transport Protocol
    BEP29: https://www.bittorrent.org/beps/bep_0029.html
    """

    def __init__(self) -> None:
        pass


PROTOCOL_NAME_v10 = b'BitTorrent protocol'  # BitTorrent v1.0
PROTOCOL_V10 = 1
PROTO_VER_MAP = {
    PROTOCOL_V10: PROTOCOL_NAME_v10,
}
PROTOCOL_VERS = {
    len(PROTOCOL_NAME_v10): PROTOCOL_V10
}


class WrongMessageError(ValueError):
    pass


class HandshakeError(ConnectionAbortedError):
    def __init__(self):
        super().__init__('Unexpected peer_id')


class _MessageBytes(bytes):
    @property
    def len(self) -> int:
        return len(self)


class Message:
    MESSAGE_ID = None
    BASE_LENGTH = 0
    PAYLOAD_OFFSET = 5
    PAYLOAD_FMT = ''
    _RE = re.compile(r'(.*)({\d+\.len})(.*)')
    _SUB = r'\1{}\3'

    def __init__(self, length_prefix: int = 0, *payload) -> None:
        self.length_prefix = length_prefix
        self.payload = payload

    def to_bytes(self) -> bytes:
        fmt = ['!I']
        args = [self.length_prefix]
        if self.MESSAGE_ID is not None:
            fmt.append('B')
            args.append(self.MESSAGE_ID)
        fmt.append(self.PAYLOAD_FMT.format(*self.payload))
        args.extend(self.payload)

        return struct.pack(''.join(fmt), *args)

    @classmethod
    def from_buf(cls, buf: io.BytesIO, buf_size: int) -> Optional['Message']:
        len_prefix = int.from_bytes(buf.read(4), 'big')
        total_len = 4 + len_prefix

        if buf_size < total_len:
            return

        buf.seek(-4, io.SEEK_CUR)
        return cls.from_bytes(buf.read(total_len))

    @classmethod
    def from_bytes(cls, buf: bytes) -> 'Message':
        if not buf:
            raise WrongMessageError('No data')

        msg_ids = {
            0: Choke,
            1: UnChoke,
            2: Interested,
            3: NotInterested,
            4: Have,
            5: Bitfield,
            6: Request,
            7: Piece,
            8: Cancel,
            9: Port,
        }
        try:
            length, msg_id = struct.unpack_from('!IB', buf)
            print(f'{length=} {msg_id=}')
        except struct.error:
            msg = KeepAlive
        else:
            msg = msg_ids.get(msg_id, Handshake)

        print(f'build {msg.__name__}')

        return msg._from_bytes(buf)

    @classmethod
    def _from_bytes(cls, buf: bytes) -> 'Message':
        length = struct.unpack_from('!I', buf)[0]
        fmt = cls._RE.sub(cls._SUB, cls.PAYLOAD_FMT).format(length - cls.BASE_LENGTH)

        return cls(*struct.unpack_from(f'!{fmt}', buf, cls.PAYLOAD_OFFSET))


class KeepAlive(Message):
    """
    <len=0000>
    """

    BASE_LENGTH = 0
    PAYLOAD_OFFSET = 0

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class Choke(Message):
    """
    <len=0001><msg_id=0>
    """

    MESSAGE_ID = 0
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class UnChoke(Message):
    """
    <len=0001><msg_id=1>
    """

    MESSAGE_ID = 1
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class Interested(Message):
    """
    <len=0001><msg_id=2>
    """

    MESSAGE_ID = 2
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class NotInterested(Message):
    """
    <len=0001><msg_id=3>
    """

    MESSAGE_ID = 3
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class Have(Message):
    """
    <len=0005><msg_id=4><piece_index=I>
    """

    MESSAGE_ID = 4
    BASE_LENGTH = 5
    PAYLOAD_FMT = 'I'

    def __init__(self, piece_index: int):
        super().__init__(self.BASE_LENGTH, piece_index)

    @property
    def piece_index(self) -> int:
        return self.payload[0]


class Bitfield(Message):
    """
    <len=0001 + X><msg_id=5><bitfield=?s>
    """

    MESSAGE_ID = 5
    BASE_LENGTH = 1
    PAYLOAD_FMT = '{0.len}s'

    def __init__(self, bitfield: bytes):
        bitfield = _MessageBytes(bitfield)
        super().__init__(self.BASE_LENGTH + bitfield.len, bitfield)

    @property
    def bitfield(self) -> bytes:
        return self.payload[0]


class Request(Message):
    """
    <len=0013><msg_id=6><index=I><begin=I><length=I>
    """

    MESSAGE_ID = 6
    BASE_LENGTH = 13
    PAYLOAD_FMT = '3I'

    def __init__(self, index: int, begin: int, length: int):
        super().__init__(self.BASE_LENGTH, index, begin, length)

    @property
    def index(self) -> int:
        return self.payload[0]

    @property
    def begin(self) -> int:
        return self.payload[1]

    @property
    def length(self) -> int:
        return self.payload[2]


class Piece(Message):
    """
    <len=0009 + X><msg_id=7><index=I><begin=I><block=?s>
    """

    MESSAGE_ID = 7
    BASE_LENGTH = 9
    PAYLOAD_FMT = 'II{2.len}s'

    def __init__(self, index: int, begin: int, block: bytes):
        block = _MessageBytes(block)
        super().__init__(self.BASE_LENGTH + block.len, index, begin, block)

    @property
    def index(self) -> int:
        return self.payload[0]

    @property
    def begin(self) -> int:
        return self.payload[1]

    @property
    def block(self) -> bytes:
        return self.payload[2]


class Cancel(Message):
    """
    <len=0013><msg_id=8><index=I><begin=I><length=I>
    """

    MESSAGE_ID = 8
    BASE_LENGTH = 13
    PAYLOAD_FMT = '3I'

    def __init__(self, index: int, begin: int, length: int):
        super().__init__(self.BASE_LENGTH, index, begin, length)

    @property
    def index(self) -> int:
        return self.payload[0]

    @property
    def begin(self) -> int:
        return self.payload[1]

    @property
    def length(self) -> int:
        return self.payload[2]


class Port(Message):
    """
    <len=0003><msg_id=9><listen_port=H>
    """

    MESSAGE_ID = 9
    BASE_LENGTH = 3
    PAYLOAD_FMT = 'H'

    def __init__(self, listen_port):
        super().__init__(self.BASE_LENGTH, listen_port)

    @property
    def listen_port(self) -> int:
        return self.payload[0]


class Handshake(Message):
    """
    <pstr_len=B><pstr=?s><reserved=Q><info_hash=20s><peer_id=20s>
    """

    PAYLOAD_FMT = '!B{0.len}sQ20s20s'

    def __init__(self, reserved: int, info_hash: bytes, peer_id: bytes, version=1):
        pstr = _MessageBytes(PROTO_VER_MAP[version])
        super().__init__(pstr.len, pstr, reserved, info_hash, peer_id)

    @classmethod
    def _from_bytes(cls, buf: bytes) -> 'Handshake':
        name_len = buf[0]
        proto_ver = PROTOCOL_VERS.get(name_len)
        if not proto_ver:
            # raise WrongMessageError(f'Unsupported protocol: {buf[1:name_len + 1].decode("ascii", "replace")}')
            raise WrongMessageError(f'Unrecognized Message or Unsupported protocol: '
                                    f'{buf[:16]}{"..." if len(buf) > 16 else ""}')

        return cls(*struct.unpack_from('!Q20s20s', buf, 1 + name_len), proto_ver)

    def to_bytes(self) -> bytes:
        return struct.pack(self.PAYLOAD_FMT.format(*self.payload),
                           self.length_prefix, *self.payload)

    @property
    def reserved(self):
        return self.payload[1]

    @property
    def info_hash(self):
        return self.payload[2]

    @property
    def peer_id(self):
        return self.payload[3]


class PeerWireProtocol:
    KEEP_ALIVE_TIMEOUT = 120
    KEEP_ALIVE_BIAS = 5

    def __init__(self, peer_id: bytes, ip: str, port: int):
        self.peer_id = peer_id
        self.peer_addr = ip, port

        self.sock: Optional[sk.socket] = None

    def connect(self):
        print(f'connect to peer {self.peer_addr}')
        ipa = ipaddress.ip_address(self.peer_addr[0])
        family = sk.AF_INET if ipa.version == 4 else sk.AF_INET6
        self.sock = sk.socket(family, sk.SOCK_STREAM)
        self.sock.settimeout(5)
        try:
            self.sock.connect(self.peer_addr)
        except sk.error:
            self.disconnect()
            raise

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _send_message(self, msg: Message) -> Message:
        if not self.sock:
            self.connect()

        print(f'send {msg.__class__.__name__}')
        self.sock.send(msg.to_bytes())

        try:
            resp = self.sock.recv(65536)
            print(f'received {len(resp)} bytes')
        except sk.error:
            self.disconnect()
            raise

        try:
            return Message.from_bytes(resp)
            # TODO: extended by <reserved & (1 << 20)>
            #   resp[<msg_len>:]
        except WrongMessageError as e:
            self.disconnect()
            raise ConnectionAbortedError(e)

    def handshake(self, info_hash: bytes, client_peer_id: bytes, reserved: int = 0) -> Tuple[bytes, bytes]:
        resp = self._send_message(Handshake(reserved, info_hash, client_peer_id))

        if self.peer_id and resp.peer_id and self.peer_id == resp.peer_id:
            self.disconnect()
            raise HandshakeError

        return resp.peer_id, resp.reserved

    def bitfield(self, bitfield: bytes):
        return self._send_message(Bitfield(bitfield))

    def run(self, reserved: int, info_hash: bytes, client_peer_id: bytes, bitfield: bytes):
        resp = self._send_message(Handshake(reserved, info_hash, client_peer_id))

        if self.peer_id and resp.peer_id and self.peer_id == resp.peer_id:
            self.disconnect()
            raise HandshakeError

        # TODO: save actual peer_id and reserved

        resp = self._send_message(Bitfield(bitfield))
        # TODO: save received bitfield

        # TODO: ...
