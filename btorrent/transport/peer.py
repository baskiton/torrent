import enum
import ipaddress
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
PROTO_VER_MAP = {
    1: PROTOCOL_NAME_v10,
}
PROTOCOL_VERS = {
    len(PROTOCOL_NAME_v10): 1
}


class WrongMessageError(ValueError):
    pass


class Message:
    MESSAGE_ID = None
    PAYLOAD_FMT = ''

    def __init__(self, length_prefix: int, payload_fmt: str = '', *payload) -> None:
        self.length_prefix = length_prefix
        self.payload_fmt = payload_fmt
        self.payload = payload

    def to_bytes(self) -> bytes:
        fmt = ['!I']
        args = [self.length_prefix]
        if self.MESSAGE_ID is not None:
            fmt.append('B')
            args.append(self.MESSAGE_ID)
        fmt.append(self.payload_fmt)
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

        return msg.from_bytes(buf)


class KeepAlive(Message):

    @classmethod
    def from_bytes(cls, buf: bytes) -> 'KeepAlive':
        try:
            if not struct.unpack_from('!I', buf):
                return cls(0)
        except struct.error:
            pass
        raise WrongMessageError


class Choke(Message):
    MESSAGE_ID = 0

    def __init__(self):
        super().__init__(1)


class UnChoke(Message):
    MESSAGE_ID = 1

    def __init__(self):
        super().__init__(1)


class Interested(Message):
    MESSAGE_ID = 2

    def __init__(self):
        super().__init__(1)


class NotInterested(Message):
    MESSAGE_ID = 3

    def __init__(self):
        super().__init__(1)


class Have(Message):
    MESSAGE_ID = 4

    def __init__(self, piece_index: int):
        super().__init__(5, 'I', piece_index)


class Bitfield(Message):
    MESSAGE_ID = 5

    def __init__(self, bitfield: bytes):
        super().__init__(1 + len(bitfield), f'{len(bitfield)}s', bitfield)


class Request(Message):
    MESSAGE_ID = 6

    def __init__(self, index: int, begin: int, length: int):
        super().__init__(13, '3I', index, begin, length)


class Piece(Message):
    MESSAGE_ID = 7

    def __init__(self, index: int, begin: int, block: bytes):
        super().__init__(9 + len(block), f'II{len(block)}s', index, begin, block)


class Cancel(Message):
    MESSAGE_ID = 8

    def __init__(self, index: int, begin: int, length: int):
        super().__init__(13, '3I', index, begin, length)


class Port(Message):
    MESSAGE_ID = 9

    def __init__(self, listen_port):
        super().__init__(3, 'H', listen_port)


class _Handshake(Message):
    def __init__(self, version, reserved, info_hash: bytes, peer_id: bytes):
        pstr = PROTO_VER_MAP[version]
        super().__init__(len(pstr), pstr)


class Handshake:
    def __init__(self, protocol_name: bytes):
        self.protocol_name = protocol_name
        proto_name_len = len(protocol_name)
        self.__struct = struct.Struct(f'!B{proto_name_len}sQ20s20s')

    def pack(self, reserved: int, info_hash: bytes, peer_id: bytes) -> bytes:
        return self.__struct.pack(len(self.protocol_name), self.protocol_name,
                                  reserved, info_hash, peer_id)

    def unpack(self, buf: bytes, peer_id: bytes) -> Tuple[bytes, bytes]:
        name_len = buf[0]
        if name_len != len(self.protocol_name):
            raise ValueError(f'Unsupported protocol: {buf[1:name_len + 1].decode("ascii", "replace")}')

        name_len, name, reserved, ih, pid = self.__struct.unpack_from(buf)
        if pid and peer_id and pid != peer_id:
            raise ValueError('Unexpected peer_id')

        return pid, reserved


class PeerWireProtocol:
    PROTOCOL_NAME = b'BitTorrent protocol'  # BitTorrent v1.0
    HANDSHAKE = Handshake(PROTOCOL_NAME)

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

    def _send(self, data: bytes):
        if not self.sock:
            self.connect()

        print('send')
        self.sock.send(data)

    def handshake(self, info_hash: bytes, peer_id: bytes, reserved: int = 0) -> Tuple[bytes, bytes]:
        req = self.HANDSHAKE.pack(reserved, info_hash, peer_id)
        self._send(req)

        try:
            resp = self.sock.recv(8192)
        except sk.error:
            self.disconnect()
            raise

        try:
            peer_id, reserved = self.HANDSHAKE.unpack(resp, peer_id)
        except ValueError as e:
            self.disconnect()
            raise ConnectionAbortedError(e)

        # TODO: extended by <reserved & (1 << 20)>
        #   resp[struct.calcsize(self.HANDSHAKE_FMT):]

        return peer_id, reserved
