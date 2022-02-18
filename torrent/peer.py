import hashlib


class Peer:
    def __init__(self, ip, port: int, peer_id: bytes = None):
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.status = None
        self.id = int.from_bytes(hashlib.sha256(str((self.ip, self.port)).encode()).digest(),
                                 'big', signed=False)

    def __repr__(self):
        return f'Peer({self.ip}:{self.port})'
