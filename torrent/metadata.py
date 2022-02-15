import hashlib
import pathlib

from typing import List


class TorrentMetadata:
    def __init__(self, metadata: dict):
        self.announce: str = metadata[b'announce'].decode('utf8')
        self.announce_list: List[List[bytes]] = metadata.get(b'announce-list')
        x = metadata.get(b'comment')
        if x is not None:
            x = x.decode('utf8')
        self.comment: str = x
        x = metadata.get(b'created by')
        if x is not None:
            x = x.decode('utf8')
        self.created_by: str = x
        x = metadata.get(b'creation date')
        self.creation_date: int = x and int(x)
        self.encoding: str = metadata.get(b'encoding', b'utf8').decode('utf8')
        x = metadata.get(b'publisher')
        if x is not None:
            x = x.decode('utf8')
        self.publisher: str = x
        x = metadata.get(b'publisher-url')
        if x is not None:
            x = x.decode('utf8')
        self.publisher_url: str = x
        self.info = MetadataInfo.from_rawdata(metadata.get(b'info'), self.encoding)


class MetadataInfo:
    def __init__(self, pieces: bytes, piece_length: int, private: int,
                 name: pathlib.Path, files: List['MetadataFile'], total_size: int, info_hash: bytes = None):
        # common
        self.pieces = pieces
        self.piece_length = piece_length
        self.private = private

        self.name = name
        self.files = files
        self.total_size = total_size

        # additional
        self.hashes = tuple(pieces[i:i+20] for i in range(0, len(pieces), 20))
        self.pieces_amount = len(self.hashes)   # math.ceil(total_size / pieces_length)
        self.info_hash = info_hash

    @classmethod
    def from_rawdata(cls, info: dict, encoding):
        # common
        pieces = info.get(b'pieces')
        piece_length = int(info.get(b'piece length'))
        private = int(info.get(b'private', 0))

        name = pathlib.Path(info.get(b'name').decode(encoding))
        files = []
        total_size = 0

        length = info.get(b'length')
        if length is not None:
            files.append(MetadataFile(name, int(length), info.get(b'md5sum')))
            name = pathlib.Path()
            total_size = length
        else:
            for f_info in info.get(b'files', ()):
                path = pathlib.Path(*map(lambda s: s.decode(encoding), f_info.get(b'path')))
                sz = int(f_info.get(b'length'))
                total_size += sz
                files.append(MetadataFile(path, sz, f_info.get(b'md5sum')))

        return cls(pieces, piece_length, private, name, files, total_size)


class MetadataFile:
    def __init__(self, path: pathlib.Path, length: int, md5sum: bytes = None):
        self.path = path
        self.length = length
        self.md5sum = md5sum

    # def __repr__(self):
    #     return f'MetadataFile<{self.path}; {self.length} bytes; md5={self.md5sum}>'
