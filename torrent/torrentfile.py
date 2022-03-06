import pathlib

from torrent import bencode, metadata


class TorrentFile:
    def __init__(self, data: metadata.TorrentMetadata) -> None:
        self.metadata = data

    @property
    def info_hash(self) -> bytes:
        return self.metadata.info.info_hash

    @property
    def total_size(self) -> int:
        return self.metadata.info.total_size

    @classmethod
    def from_file(cls, fname: pathlib.Path) -> 'TorrentFile':
        return cls(metadata.TorrentMetadata(bencode.decode_from_file(fname)))
