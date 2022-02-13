import io
import string

from typing import BinaryIO, Union

_INT = b'i'
_LIST = b'l'
_DICT = b'd'
_END = b'e'
_SEP = b':'


def _decode_int(stream: io.BytesIO) -> int:
    i = b''
    _ = stream.read(1)
    while _ != _END:
        if not _:
            raise EOFError()
        i += _
        _ = stream.read(1)
    return int(i)


def _decode_bytes(stream: io.BytesIO) -> bytes:
    stream.seek(-1, io.SEEK_CUR)
    sz = b''
    _ = stream.read(1)
    while _ != _SEP:
        if not len(_):
            raise EOFError()
        if not _.isdigit():
            raise ValueError(f'Expected digit, got `{_}` instead')
        sz += _
        _ = stream.read(1)
    return stream.read(int(sz))


def _decode_list(stream: io.BytesIO) -> list:
    res = []
    v = _decode(stream)
    while v is not None:
        res.append(v)
        v = _decode(stream)
    return res


def _decode_dict(stream: io.BytesIO) -> dict:
    res = {}
    k = _decode(stream)
    while k is not None:
        if not isinstance(k, bytes):
            raise TypeError(f'`bytes` expected, got {type(k)} instead. {k}')
        res[k] = _decode(stream)
        k = _decode(stream)
    return res


def _decode_end(stream: io.BytesIO) -> None:
    return


_TYPES = {
    _INT: _decode_int,
    _LIST: _decode_list,
    _DICT: _decode_dict,
    _END: _decode_end,
}
_TYPES.update({i.encode(): _decode_bytes for i in string.digits})


def _decode(stream: Union[io.BytesIO, BinaryIO]):
    t = stream.read(1)
    res = _TYPES[t](stream)
    return res


def decode_from_file(fname: str):
    with open(fname, 'rb') as f:
        return _decode(f)


def decode_from_buffer(buf: bytes):
    return _decode(io.BytesIO(buf))
