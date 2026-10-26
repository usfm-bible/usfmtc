""" Flattened LDML files, fetched from SIL's LDML server and kept in a cache """

import os, re, sys, logging
import xml.etree.ElementTree as et
from typing import Optional, Callable

logger = logging.getLogger(__name__)

ldmlserver = "https://ldml.api.sil.org/{}"      # gives the flattened LDML for a tag
_tagre = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

def cachedir() -> str:
    """ The directory holding cached LDML files: USFMTC_CACHE, else the
        platform's user cache directory, with ldml/ under it """
    res = os.environ.get("USFMTC_CACHE", "")
    if not res:
        if sys.platform == "win32":
            res = os.path.join(os.environ.get("LOCALAPPDATA", "") or os.path.expanduser("~"), "usfmtc", "cache")
        elif sys.platform == "darwin":
            res = os.path.expanduser("~/Library/Caches/usfmtc")
        else:
            res = os.path.join(os.environ.get("XDG_CACHE_HOME", "") or os.path.expanduser("~/.cache"), "usfmtc")
    return os.path.join(res, "ldml")

def fetchldml(lang: str) -> bytes:
    """ Downloads the flattened LDML for lang from the server """
    from urllib.request import urlopen
    from urllib.parse import quote
    with urlopen(ldmlserver.format(quote(lang)), timeout=30) as inf:
        return inf.read()

_ldmls = {}     # file path -> parsed ElementTree

def getFlatLdml(lang: str, ldmldir: Optional[str] = None, refresh: bool = False,
                fetch: Optional[Callable[[str], bytes]] = None) -> et.ElementTree:
    """ The flattened LDML for lang, from ldmldir (default cachedir()). If it is
        not there, or refresh, it is got with fetch (default fetchldml) and kept
        there. Raises ValueError for a bad tag or bad data, and OSError if it
        can't be got. """
    if not _tagre.fullmatch(lang):
        raise ValueError(f"Bad language tag {lang!r}")
    ldmldir = ldmldir or cachedir()
    path = os.path.join(ldmldir, lang + ".xml")
    if refresh or not os.path.exists(path):
        logger.info(f"Fetching the LDML for {lang}")
        data = (fetch or fetchldml)(lang)
        try:
            et.fromstring(data)             # don't keep what isn't xml
        except et.ParseError as err:
            raise ValueError(f"Bad LDML for {lang}: {err}")
        os.makedirs(ldmldir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as outf:
            outf.write(data)
        os.replace(tmp, path)
        _ldmls.pop(path, None)
    if path not in _ldmls:
        _ldmls[path] = et.parse(path)
    return _ldmls[path]
