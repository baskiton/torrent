import http.client
import urllib.parse
import urllib.request

from torrent import __version__, bencode


def http_request(url: urllib.parse.ParseResult, params: dict = None, headers: dict = None):
    # BEP3: https://www.bittorrent.org/beps/bep_0003.html

    query = urllib.parse.urlencode(params or {})
    req = urllib.request.Request(f'{url.geturl()}{url.query and "&" or "?"}{query}', method='GET', headers=headers or {})
    req.add_header('User-agent', f'pyTorrent/{__version__} by baskiton')
    with urllib.request.urlopen(req) as r:
        r: http.client.HTTPResponse
        response = r.read()
    try:
        result = bencode.decode_from_buffer(response)
    except (ValueError, TypeError, EOFError) as e:
        raise ValueError(f'{e}: {response}')
    failure = result.get(b'failure reason')
    if failure:
        raise ValueError(failure.decode())
    return result


def udp_request(url: urllib.parse.ParseResult):
    # BEP15: https://www.bittorrent.org/beps/bep_0015.html

    raise NotImplementedError
