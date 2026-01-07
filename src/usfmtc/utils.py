
import os
import logging
import traceback

logger = logging.getLogger(__name__)

def readsrc(src, errors="replace"):
    if hasattr(src, "read"):
        return src.read()
    elif not isinstance(src, str):      # we're a parsed xml doc
        return src
    elif os.path.exists(src):
        with open(src, encoding="utf-8", errors=errors) as inf:
            data = inf.read()
        return data
    elif "\n" in src or len(src) > 127:
        return src
    else:
        raise FileNotFoundError

def getSrcName(src):
    if hasattr(src, "name"):
        return src.name
    elif not isinstance(src, str):
        return ""
    elif os.path.isfile(src):
        return src
    else:
        return ""

def get_trace():
    return traceback.format_stack()
