import hashlib


class Peer:
    def __init__(self, ip, port: int, peer_id: bytes = None) -> None:
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.status = None
        self.id = hashlib.sha256(str((self.ip, self.port)).encode()).digest()

    def __hash__(self):
        return int.from_bytes(self.id, 'little')

    def __eq__(self, other: 'Peer') -> bool:
        return self.id == other.id

    def __repr__(self) -> str:
        return f'Peer({self.ip}:{self.port})'
