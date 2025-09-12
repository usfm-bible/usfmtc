
import re
from usfmtc.reference import Ref
from usfmtc.usfmparser import WS

def usvout(m):
    u = ord(m.group(1))
    if u > 0xFFFF:
        return "\\U{:08X}".format(u)
    else:
        return "\\u{:04X}".format(u)

_reesc = re.compile(r'([\\|]|//)')
_reatt = re.compile(r'([\\|"])')
def attribescaped(s, escapes):
    return escaped(s, escapes, reg=_reatt)

def escaped(s, escapes, reg=None):
    res = (reg or _reesc).sub(r'\\\1', s)
    if escapes:
        res = re.sub(r'([{}])'.format(escapes), usvout, res)
    return res

def proc_start_ms(el, tag, pref, emit, ws, escapes, version):
    if "style" not in el.attrib:
        return
    extra = ""
    if version < [3, 2]:
        if "altnumber" in el.attrib:
            extra += " \\{0}a {1}\\{0}a*".format(pref, el.get("altnumber"))
        if "pubnumber" in el.attrib:
            extra += " \\{0}p {1}{2}".format(pref, escaped(el.get("pubnumber"), escapes), "\n" if pref == "c" else "\\"+pref+"p*")
        emit("\\{0} {1}{2}{3}".format(el.get("style"), el.get("number"), extra, ws))
    else:
        emit("\\{}".format(el.get("style")))
        append_attribs(el, emit, init=True)
        emit(" {0}{1}{2}".format(el.get("number"), extra, ws))

excludes = ["style", "status", "title", "caller", "number", "code", "version"]

def append_attribs(el, emit, attribmap={}, tag=None, nows=False, escapes="", init=False, excludes=excludes):
    s = el.get('style', el.tag)
    if tag is not None and type(tag) != tuple:
        tag = (tag, tag)
    at_start = tag is None and not nows
    if tag is None:
        l = list(el.attrib.items())
    elif tag[1] not in el.attrib:
        return
    else:
        l = [(tag[0], el.get(tag[1], ""))]
    l = [(k, v) for k,v in l if k not in excludes]
    if not len(l):
        return
    final = "|" if init else ""
    if len(l) == 1 and l[0][0] == attribmap.get(s, ''):
        emit("|"+attribescaped(l[0][1], escapes)+final)
    else:
        attribs = ['{0}="{1}"'.format(k, attribescaped(v, escapes)) for k,v in l]
        if len(attribs):
            emit("|"+" ".join(attribs)+final)

def get(el, k):
    return el.get(k, "")

class Emitter:
    def __init__(self, outf, escapes):
        self.outf = outf
        self.escapes = escapes

    def __call__(self, s, text=False):
        if s is None:
            return
        s = re.sub(r"\s*\n\s*", "\n", s)
        if text:
            s = escaped(s, self.escapes)
        self.outf.write(s)

def iterels(el, events):
    if 'start' in events:
        yield ('start', el)
    for c in el:
        yield from iterels(c, events)
    if 'end' in events:
        yield ('end', el)

def _isnextref(cref, ref, e):
    if ref.chapter == cref.chapter:
        return ref.verse == cref.verse or ref.verse == cref.verse + 1
    else:
        return ref.chapter == cref.chapter + 1 and ref.verse == 1

def usx2usfm(outf, root, grammar=None, lastel=None, version=None, escapes="", forcevid=False, **kw):
    if grammar is None:
        attribmap = {}
        mcats = {}
    else:
        attribmap = grammar.attribmap
        mcats = grammar.marker_categories
    if version is None:
        vtext = root.get("version")
        if vtext:
            version = [int(x) for x in vtext.split(".")]
    if version is None:
        version = [100]
    if version < [3, 2]:
        escapes = ""
    emit = Emitter(outf, escapes)
    paraelements = ("chapter", "para", "row", "sidebar")
    cref = None
    innote = None
    for (ev, el) in iterels(root, ("start", "end")):
        s = el.get("style", "")

        if ev == "start":
            if el.tag in paraelements and s != "":
                if lastel is not None and lastel.tail is not None:
                    emit(lastel.tail.rstrip(WS), text=True)
                # emit("\n")
            elif el.tag == "table":
                if lastel is not None and lastel.tail is not None:
                    emit(lastel.tail.rstrip(WS), text=True)
            elif lastel is not None:
                emit(lastel.tail, text=True)
            lastel = None
            prespace = False
            if el.tag == "chapter":
                proc_start_ms(el, "chapter", "c", emit, "", escapes, version)
                n = int(el.get("number", 0))
                if cref is None:
                    cref = Ref(chapter=n, verse=0)
                else:
                    cref.chapter = n
                    cref.verse = 0
            elif el.tag == "verse":
                proc_start_ms(el, "verse", "v", emit, " ", escapes, version)
                v = el.get("number", "0")
                m = re.match(r"^(\d+)(\S+?)$", v)
                if m:
                    n = int(m.group(1))
                    s = m.group(2) or None
                else:
                    try:
                        n = int(v)
                        s = None
                    except ValueError:
                        n = 1
                        s = v
                if cref is None:
                    cref = Ref(verse=n, subverse=s)
                else:
                    cref.verse = n
                    cref.subverse = None
            elif el.tag == "book":
                emit("\\{0} {1}".format(s, el.get("code")))
                prespace = True
            elif el.tag in ("row", "para"):
                if 'vid' in el.attrib:
                    r = Ref(el.get("vid", ""))
                    if version < [3, 2] and (cref is None or forcevid or _isnextref(cref, r, el)):
                        emit(f"\\vid|{r}\\*\n")
                    cref = r.last
                if (el.text is None or not el.text.strip(WS)) and (len(el) and el[0].tag in paraelements):
                    emit("\\{0}\n".format(s))
                else:
                    emit("\\{0} ".format(s))
            elif el.tag in ("link", "char"):
                emit("\\{0} ".format(s))
            elif el.tag in ("note", "sidebar"):
                emit("\\{0}".format(s))
                if version >= [3, 2] and el.tag != "ms":
                    append_attribs(el, emit, attribmap=attribmap, init=True)
                if el.tag != "sidebar":
                    emit(" {} ".format(el.get("caller")))
                else:
                    emit("\n")
                if version < [3, 2] and "category" in el.attrib:
                    emit("\\cat {0}\\cat*".format(el.get("category")))
                innote = mcats.get(s, "") if el.tag == "note" else None
            elif el.tag == "unmatched":
                emit("\\" + el.get("style", " "))
            elif el.tag == "figure":
                if (v := el.get("file", None)) is not None:
                    del el.attrib["file"]
                    el.set("src", v)
                emit("\\{} ".format(s))
            elif el.tag == "cell":
                if "colspan" in el.attrib:
                    emit("\\{0}-{1} ".format(s, el.get("colspan")))
                else:
                    emit("\\{} ".format(s))
            elif el.tag == "optbreak":
                emit("//")
            elif el.tag == "ms":
                emit("\\{}".format(s))
                isbare = mcats.get(s, "") != "milestone" and len(el.attrib) == 1
                append_attribs(el, emit, attribmap=attribmap)
                emit("\\*" if not isbare else ("" if el.tail and el.tail[0] in " \n" else " ")) # protective space
            elif el.tag == "ref":
                if el.get('gen', 'false').lower() != 'true':
                    emit("\\ref ")
            elif el.tag == "usx":
                version =  el.get("version", [3,1])
                if isinstance(version, str):
                    version = [int(x.strip(WS)) for x in version.split(".")]
            elif el.tag in ("table", ):
                pass
            elif el.tag == "periph":
                name = el.get("alt", None)
                emit("\\periph" + (" "+name if name else ""))
                append_attribs(el, emit, attribmap=attribmap, excludes=["alt"])
                emit("\n")
            else:
                raise SyntaxError(el.tag)
            if version >= [3, 2] and el.tag not in ("ms", "note", "sidebar", "verse", "chapter"):
                append_attribs(el, emit, attribmap=attribmap, init=True)
            if el.text is not None and len(el.text.lstrip(WS)):
                if prespace:
                    emit(" ")
                if not(len(el)) and prespace:
                    emit(el.text.strip(WS), text=True)
                else:
                    emit(el.text.lstrip(WS), text=True)
            lastel = None
            lastopen = el

        elif ev == "end":
            if el.tag in ("para", "row", "sidebar", "book", "chapter"):
                if lastel is not None and lastel.tail is not None:
                    emit(lastel.tail.rstrip(WS), text=True)
                emit("\n")
            elif lastel is not None and lastel.tail is not None:
                emit(lastel.tail, text=True)
            if el.tag == "note":
                emit("\\{}*".format(s))
                innote = None
            elif el.tag in ("char", "link", "figure") and (not innote or mcats.get(s, "") != innote + "char"):
                if version <= [3, 1]:
                    append_attribs(el, emit, attribmap=attribmap)
                emit("\\{}*".format(s))
            elif el.tag == "sidebar":
                emit("\n\\{}e\n".format(s))
            elif el.tag == "ref" and el.get('gen', 'false').lower() != 'true':
                append_attribs(el, emit, attribmap=attribmap, nows=True)
                emit("\\ref*")
            elif el.tag == "book":
                emit("\n")
                if version >= [3, 1]:
                    emit("\\usfm {}\n".format(".".join([str(x) for x in version])))
            lastel = el
    return lastel

