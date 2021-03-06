import io
import pathlib
import string

from typing import Any, AnyStr, Iterable, Mapping, Optional, Union

_INT = b'i'
_LIST = b'l'
_DICT = b'd'
_END = b'e'
_SEP = b':'


def _decode_int(stream: io.BytesIO) -> int:
    i = io.BytesIO()
    _ = stream.read(1)
    while _ != _END:
        if not _:
            raise EOFError()
        i.write(_)
        _ = stream.read(1)
    return int(i.getvalue())


def _decode_buffer(stream: io.BytesIO) -> bytes:
    stream.seek(-1, io.SEEK_CUR)
    sz = io.BytesIO()
    _ = stream.read(1)
    while _ != _SEP:
        if not len(_):
            raise EOFError()
        if not _.isdigit():
            raise ValueError(f'Expected digit, got `{_}` instead')
        sz.write(_)
        _ = stream.read(1)
    return stream.read(int(sz.getvalue()))


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
        res[k.lower()] = _decode(stream)
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
_TYPES.update({i.encode(): _decode_buffer for i in string.digits})


def _decode(stream: io.BytesIO) -> Optional[Union[int, list, dict]]:
    t = stream.read(1)
    try:
        res = _TYPES[t](stream)
    except KeyError:
        raise ValueError('Gotten data is not bencode')
    return res


def decode_from_file(fname: pathlib.Path) -> Optional[Union[int, list, dict]]:
    return _decode(io.BytesIO(fname.read_bytes()))


def decode_from_buffer(buf: bytes) -> Optional[Union[int, list, dict]]:
    return _decode(io.BytesIO(buf))


def _encode_int(x: int, to: io.BytesIO) -> None:
    to.write(_INT)
    to.write(str(int(x)).encode())
    to.write(_END)


def _encode_buffer(x: AnyStr, to: io.BytesIO) -> None:
    if isinstance(x, str):
        x = x.encode()
    elif not isinstance(x, bytes):
        raise TypeError(f'Expected a `str` or `bytes`, got `{type(x)}` instead.')
    to.write(str(len(x)).encode())
    to.write(_SEP)
    to.write(x)


def _encode_list(x: Iterable, to: io.BytesIO) -> None:
    to.write(_LIST)
    for i in x:
        _encode(i, to)
    to.write(_END)


def _encode_dict(x: Mapping, to: io.BytesIO) -> None:
    to.write(_DICT)
    # keys of dictionary must be sorted by lexicography
    for key in sorted(x):
        _encode_buffer(key, to)
        _encode(x[key], to)
    to.write(_END)


def _encode(item: Any, to: io.BytesIO) -> None:
    if isinstance(item, int):
        _encode_int(item, to)
    elif isinstance(item, (bytes, str)):
        _encode_buffer(item, to)
    elif isinstance(item, Mapping):
        _encode_dict(item, to)
    elif isinstance(item, Iterable):
        _encode_list(item, to)
    else:
        raise TypeError(f'`{type(item)}` is not bencodable')


def encode(data, out: io.BytesIO = None) -> io.BytesIO:
    if out is None:
        out = io.BytesIO()
    _encode(data, out)
    return out
