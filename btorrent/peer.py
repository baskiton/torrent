import ipaddress

from typing import AnyStr, Union

import btorrent.transport.peer as transport


class Peer:
    def __init__(self, ip: Union[AnyStr, int], port: int, peer_id: bytes = b'') -> None:
        self.__ip = ipaddress.ip_address(ip).compressed
        self.__port = port
        self.peer_id = peer_id
        self.reserved = bytearray(8)

        self.state = transport.PeerState.CHOKED
        self.connection = transport.PeerWireProtocol(self.peer_id, self.ip, port)

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
