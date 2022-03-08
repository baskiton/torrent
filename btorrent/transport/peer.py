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


class PeerWireProtocol:
    PROTOCOL_NAME = b'BitTorrent protocol'  # BitTorrent v1.0
    PROTOCOL_NAME_LEN = len(PROTOCOL_NAME)
    HANDSHAKE_FMT = f'!B{PROTOCOL_NAME_LEN}sQ20s20s'

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
        req = struct.pack(self.HANDSHAKE_FMT, self.PROTOCOL_NAME_LEN, self.PROTOCOL_NAME, reserved,
                          info_hash, peer_id)
        self._send(req)

        try:
            resp = self.sock.recv(8192)
        except sk.error:
            self.disconnect()
            raise

        if not resp:
            self.disconnect()
            raise ConnectionAbortedError

        name_len = resp[0]
        if name_len != self.PROTOCOL_NAME_LEN:
            self.disconnect()
            raise ConnectionAbortedError(f'Unsupported protocol: {resp[1:name_len+1].decode("ascii", "replace")}')

        name_len, name, reserved, ih, peer_id = struct.unpack_from(self.HANDSHAKE_FMT, resp)
        if peer_id and self.peer_id and peer_id != self.peer_id:
            self.disconnect()
            raise ConnectionAbortedError('Unexpected peer_id')

        # TODO: extended by <reserved & (1 << 20)>
        #   resp[struct.calcsize(self.HANDSHAKE_FMT):]

        return peer_id, reserved
