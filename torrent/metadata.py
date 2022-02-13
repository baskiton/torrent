import pathlib

from typing import List


class TorrentMetadata:
    def __init__(self, metadata: dict):
        self.raw_metadata = metadata
        self.info = MetadataInfo.from_rawdata(metadata.get(b'info'), self.encoding)

    @property
    def announce(self) -> str:
        return self.raw_metadata[b'announce'].decode('utf8')

    @property
    def announce_list(self) -> List[List[bytes]]:
        return self.raw_metadata.get(b'announce-list')

    @property
    def comment(self) -> str:
        x = self.raw_metadata.get(b'comment')
        if x is not None:
            x = x.decode('utf8')
        return x

    @property
    def created_by(self) -> str:
        x = self.raw_metadata.get(b'created by')
        if x is not None:
            x = x.decode('utf8')
        return x

    @property
    def creation_date(self) -> int:
        dt = self.raw_metadata.get(b'creation date')
        return dt and int(dt)

    @property
    def encoding(self) -> str:
        return self.raw_metadata.get(b'encoding', b'utf8').decode('utf8')

    @property
    def publisher(self) -> str:
        x = self.raw_metadata.get(b'publisher')
        if x is not None:
            x = x.decode('utf8')
        return x

    @property
    def publisher_url(self) -> str:
        x = self.raw_metadata.get(b'publisher-url')
        if x is not None:
            x = x.decode('utf8')
        return x

    @property
    def _xxx(self):
        return self.raw_metadata.get(b'_xxx')


class MetadataInfo:
    def __init__(self, pieces: bytes, pieces_length: int, private: int,
                 name: pathlib.Path, files: List['MetadataFile'], total_size: int):
        # common
        self.pieces = pieces
        self.pieces_length = pieces_length
        self.private = private

        self.name = name
        self.files = files
        self.total_size = total_size

        # additional
        self.hashes = tuple(pieces[i:i+20] for i in range(0, len(pieces), 20))
        self.pieces_amount = len(self.hashes)   # math.ceil(total_size / pieces_length)

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
                files.append(MetadataFile(path, sz, info.get(b'md5sum')))

        return cls(pieces, piece_length, private, name, files, total_size)


class MetadataFile:
    def __init__(self, path: pathlib.Path, length: int, md5sum: bytes = None):
        self.path = path
        self.length = length
        self.md5sum = md5sum

    def __repr__(self):
        return f'MetadataFile<{self.path}; {self.length} bytes; md5={self.md5sum}>'
