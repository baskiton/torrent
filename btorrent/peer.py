class Peer:
    def __init__(self, ip, port: int, peer_id: bytes = None) -> None:
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.status = None
        self.__id = self.ip, self.port

    def __hash__(self):
        return hash(self.__id)

    def __eq__(self, other: 'Peer') -> bool:
        return self.__id == other.__id

    def __repr__(self) -> str:
        return f'Peer({self.ip}:{self.port})'
