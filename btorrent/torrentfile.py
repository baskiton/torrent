import pathlib

from btorrent import bencode, metadata


class TorrentFile:
    def __init__(self, data: metadata.TorrentMetadata, file_name: pathlib.Path = None) -> None:
        self.metadata = data
        self.file_name = file_name

    @property
    def info_hash(self) -> bytes:
        return self.metadata.info.info_hash

    @property
    def total_size(self) -> int:
        return self.metadata.info.total_size

    @classmethod
    def from_file(cls, fname: pathlib.Path) -> 'TorrentFile':
        return cls(metadata.TorrentMetadata(bencode.decode_from_file(fname)), fname)
