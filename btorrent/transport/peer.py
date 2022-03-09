import enum
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


@enum.unique
class PeerState(enum.IntEnum):
    CHOKED = 0
    INTERESTED = 1


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
    def from_bytes(cls, buf: bytes) -> 'Message':
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
        except struct.error:
            msg = KeepAlive
        else:
            msg = msg_ids.get(msg_id, Handshake)

        return msg._from_bytes(buf)

    @classmethod
    def _from_bytes(cls, buf: bytes) -> 'Message':
        # return cls()
        length = struct.unpack_from('!I', buf)[0]
        fmt = cls._RE.sub(cls._SUB, cls.PAYLOAD_FMT).format(length - cls.BASE_LENGTH)

        return cls(*struct.unpack_from(f'!{fmt}', buf, cls.PAYLOAD_OFFSET))


class KeepAlive(Message):
    BASE_LENGTH = 0
    PAYLOAD_OFFSET = 0

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class Choke(Message):
    MESSAGE_ID = 0
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class UnChoke(Message):
    MESSAGE_ID = 1
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class Interested(Message):
    MESSAGE_ID = 2
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class NotInterested(Message):
    MESSAGE_ID = 3
    BASE_LENGTH = 1

    def __init__(self):
        super().__init__(self.BASE_LENGTH)


class Have(Message):
    MESSAGE_ID = 4
    BASE_LENGTH = 5
    PAYLOAD_FMT = 'I'

    def __init__(self, piece_index: int):
        super().__init__(self.BASE_LENGTH, piece_index)

    @property
    def piece_index(self) -> int:
        return self.payload[0]


class Bitfield(Message):
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
    MESSAGE_ID = 9
    BASE_LENGTH = 3
    PAYLOAD_FMT = 'H'

    def __init__(self, listen_port):
        super().__init__(self.BASE_LENGTH, listen_port)

    @property
    def listen_port(self) -> int:
        return self.payload[0]


class Handshake(Message):
    PAYLOAD_FMT = '!B{0.len}sQ20s20s'

    def __init__(self, reserved, info_hash: bytes, peer_id: bytes, version=1):
        pstr = _MessageBytes(PROTO_VER_MAP[version])
        super().__init__(pstr.len, pstr, reserved, info_hash, peer_id)

    @classmethod
    def _from_bytes(cls, buf: bytes) -> 'Handshake':
        name_len = buf[0]
        proto_ver = PROTOCOL_VERS.get(name_len)
        if not proto_ver:
            raise WrongMessageError(f'Unsupported protocol: {buf[1:name_len + 1].decode("ascii", "replace")}')

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
    def __init__(self, peer_id: bytes, ip: str, port: int):
        self.peer_id = peer_id
        self.addr = ip, port

        self.sock: Optional[sk.socket] = None

    def connect(self):
        print(f'connect to peer {self.addr}')
        ipa = ipaddress.ip_address(self.addr[0])
        family = sk.AF_INET if ipa.version == 4 else sk.AF_INET6
        self.sock = sk.socket(family, sk.SOCK_STREAM)
        self.sock.settimeout(5)
        try:
            self.sock.connect(self.addr)
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
            resp = self.sock.recv(8192)
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

    def handshake(self, info_hash: bytes, peer_id: bytes, reserved: int = 0) -> Tuple[bytes, bytes]:
        resp = self._send_message(Handshake(reserved, info_hash, peer_id))

        return resp.peer_id, resp.reserved
