import io
import struct

import bitstring
import errno
import ipaddress
import socket as sk
import time

from typing import AnyStr, Generator, Optional, Union

import btorrent.transport.peer as transport


class Peer:
    CONNECT_TIMEOUT = 5

    def __init__(self, ip: Union[AnyStr, int], port: int, peer_id: bytes = b'') -> None:
        self.__ip = ipaddress.ip_address(ip).compressed
        self.__port = port
        self.peer_id = peer_id
        self.reserved = bytearray(8)
        self.bitfield = bitstring.BitArray()

        self.state = {
            'handshaked': False,
            'bitfielded': False,
            'destroyed': False,
            'am_choking': True,
            'am_interested': False,
            'peer_choking': True,
            'peer_interested': False,
        }
        self.sock: Optional[sk.socket] = None
        self.last_connecting_time = 0

    @property
    def handshaked(self) -> bool:
        return self.state['handshaked']

    @handshaked.setter
    def handshaked(self, val: bool) -> None:
        self.state['handshaked'] = val

    @property
    def bitfielded(self) -> bool:
        return self.state['bitfielded']

    @bitfielded.setter
    def bitfielded(self, val: bool) -> None:
        self.state['bitfielded'] = val

    @property
    def destroyed(self) -> bool:
        return self.state['destroyed']

    @destroyed.setter
    def destroyed(self, val: bool) -> None:
        self.state['destroyed'] = val

    @property
    def am_choking(self) -> bool:
        return self.state['am_choking']

    @am_choking.setter
    def am_choking(self, val: bool) -> None:
        self.state['am_choking'] = val

    @property
    def am_interested(self) -> bool:
        return self.state['am_interested']

    @am_interested.setter
    def am_interested(self, val: bool) -> None:
        self.state['am_interested'] = val

    @property
    def peer_choking(self) -> bool:
        return self.state['peer_choking']

    @peer_choking.setter
    def peer_choking(self, val: bool) -> None:
        self.state['peer_choking'] = val

    @property
    def peer_interested(self) -> bool:
        return self.state['peer_interested']

    @peer_interested.setter
    def peer_interested(self, val: bool) -> None:
        self.state['peer_interested'] = val

    @property
    def ip(self) -> str:
        return self.__ip

    @property
    def port(self) -> int:
        return self.__port

    def __hash__(self):
        return hash((self.ip, self.port))

    def __eq__(self, other: 'Peer') -> bool:
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f'Peer({self.ip}:{self.port}, peer_id={self.peer_id})'

    def fileno(self) -> int:
        return self.sock.fileno() if self.sock else -1

    def connect(self):
        if self.handshaked or self.destroyed:
            return

        try:
            s = sk.create_connection((self.ip, self.port), self.CONNECT_TIMEOUT)
            s.setblocking(False)
        except sk.error as e:
            # TODO: log it
            print(f'Failed to connect to {self}: {e}')
            self.destroyed = True
        else:
            self.sock = s
            # TODO: log it
            print(f'{self} connected')

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            self.handshaked = False
            # TODO: log it
            print(f'{self} disconnected')

    def send_message(self, msg: transport.Message, force=False):
        if not self.sock:
            self.connect()

        if self.destroyed or not (force or self.handshaked):
            return

        try:
            self.sock.send(msg.to_bytes())
            self.last_connecting_time = time.monotonic()
        except (sk.error, Exception) as e:
            # TODO: log it
            print(f'Failed to send {msg.__class__.__name__} to {self}: {e}')
            self.destroyed = True

    def do_keep_alive(self):
        self.send_message(transport.KeepAlive())

    def do_handshake(self, info_hash: bytes, client_peer_id: bytes, reserved=0, force=False):
        self.send_message(transport.Handshake(reserved, info_hash, client_peer_id), force)

    def do_bitfield(self, bitfield: bitstring.BitArray):
        if not self.bitfielded:
            self.send_message(transport.Bitfield(bitfield.tobytes()))

    def _recv(self) -> io.BytesIO:
        buf = io.BytesIO()

        while True:
            try:
                x = self.sock.recv(8192)
                if not x:
                    break
                buf.write(x)
            except sk.error as e:
                if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # TODO: log it
                    print(f'Recv from {self} failed: {e}')
                break

        return buf

    def get_message(self) -> Generator[transport.Message]:
        buf = self._recv()
        sz = buf.tell()
        buf.seek(0)

        while sz > 4 and not self.destroyed:
            try:
                yield transport.Message.from_buf(buf, sz)
            except (transport.WrongMessageError, struct.error) as e:
                # TODO: log it
                print(f'Getting message from {self} failed: {e}')
                break
