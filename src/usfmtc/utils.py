
import os

def readsrc(src):
    if hasattr(src, "read"):
        return src.read()
    elif not isinstance(src, str):      # we're a parsed xml doc
        return src
    elif len(src) < 128 and os.path.exists(src):
        with open(src, encoding="utf-8") as inf:
            data = inf.read()
        return data
    elif "\n" in src or len(src) > 127:
        return src
    else:
        raise FileNotFoundError(src)

