
import re
from dataclasses import dataclass
from usfmtc.xmlutils import isempty
from usfmtc.usfmparser import Grammar, WS
from usfmtc.reference import Ref, RefRange, MarkerRef
import xml.etree.ElementTree as et
from typing import Optional

# This should be read from usx.rng
allpartypes = {
    'Section': """ms mse ms1 ms2 ms2e ms3 ms3e mr s s1 s2 s3 s4 s1e s2e s3e s4e sr r sp
                    sd sd1 sd2 sd3 sd4 periph iex ip mte mte1 mte2 cl cd""",
    'NonVerse': """lit cp pb p1 p2 k1 k2 rem sts qa"""
}

partypes = {e: k for k, v in allpartypes.items() for e in v.split()}

def _addvids(lastp, endp, base, v, endv, atend=False):
    res = lastp
    lastp = lastp.getnext()
    pending = []
    while lastp is not None:
        if lastp.tag == "chapter":
            break
        if lastp.tag not in ('para', 'table', 'row'):
            if id(lastp) == id(endp):
                break
            lastp = lastp.getnext()
            continue
        if lastp.tag == 'para' and partypes.get(lastp.get('style', None), None) in ("Section", "NonVerse") \
                or (not len(lastp) and (lastp.text is None or lastp.text.strip(WS) == "")):
            pending.append(lastp)
        elif id(lastp) != id(endp) or atend or endp[0].tag != "verse" or (endp.text is not None and endp.text.strip(WS) != ""):
            for p in pending:
                p.set('vid', v)
            pending = []
            lastp.set('vid', v)
            res = lastp
        if id(lastp) == id(endp):
            break
        lastp = lastp.getnext()
    if id(res) == id(endp) and base is not None:
        base.addprevious(endv)
    elif res.tag == "table":
        lastr = res
        if len(res):
            while len(lastr[-1]):
                lastr = lastr[-1]
        lastr.append(endv)
    else:
        res.append(endv)
    return res

def addesids(root, force=False):
    lastv = None
    if root.get('version', None) is None:
        root.set('version', '3.0')
    bkel = root.find('./book')
    if bkel is None:
        return
    bk = bkel.get('code', 'UNK').upper()
    bkel.set('code', bk)
    currchap = 0
    lastp = None
    lastev = None
    for v in list(root.iter()):
        if v.tag == "chapter":
            currchap = v.get('number')
            currverse = 0
            v.set('sid', "{} {}".format(bk, currchap))
            continue
        elif v.tag == "para":
            lastp = v
            continue
        elif v.tag != "verse":
            continue
        elif v.get('eid', None) is not None:
            if force:
                lastev = v
            else:
                lastv = None
            continue
        currverse = v.get('number')
        v.set('sid', "{} {}:{}".format(bk, currchap, currverse))
        if lastv is None:
            lastv = v
            continue
        eid = lastv.get('sid', None)
        if lastev is not None:
            lastev.set('eid', eid or "")
            lastev = None
        else:
            ev = v.makeelement('verse', {'eid': eid or ""})
            pv = v.getparent()
            pl = lastv.getparent()
            if id(pv) == id(pl):
                v.addprevious(ev) 
            else:
                endp = _addvids(pl, pv, v, eid, ev)
        lastv = v
    if lastv is not None and lastp is not None:
        eid = lastv.get('sid', None)
        ev = lastv.makeelement('verse', {'eid': eid or ''})
        _addvids(lastv.getparent(), lastp, None, eid, ev, atend=True)

    lastc = None
    for c in root.findall('.//chapter'):
        if lastc is not None:
            cel = c.makeelement('chapter', {'eid': lastc.get('sid', '')})
            c.addprevious(cel)
        lastc = c
    if lastc is not None:
        root.append(lastc.makeelement('chapter', {'eid': lastc.get('sid', '')}))
    return root

def addindexes(root):
    chapters = [0]
    ids = {}
    def keygen(s):
        return re.sub(r"\s", "", s)
    def donode(e):
        for i, c in enumerate(e):
            if 'aid' in c.attrib:
                ids["a."+c.get('aid', '')] = c
            if c.tag == "char" and c.get("style", "") == "k":
                v = c.get("key", keygen(c.text))
                ids["k."+v] = c
            elif e.tag == "chapter":
                n = e.get("number", 0)
                if n >= len(chapters):
                    chapters.extend([chapters[-1]] * (n - len(chapters) + 1))
                chapters[n] = c
            donode(c)
    donode(root)
    return chapters, ids

escapes = {
    '\\' : '\\',
    'n': '\n'
}

def add_specials(t, node, parent, istext=False):
    if t is None:
        return t
    t = re.sub(r'\\(.)', lambda m: escapes.get(m.group(1), "\\"+m.group(1)), t)
    if "~" in t:
        t = t.replace("~", "\u00A0")
    return t

alignments = {
    "c": "start", "cc": "centre", "cr": "end",
    "h": "start", "hc": "centre", "hr": "end"
}
_wssre = re.compile(r"^[ \t\n]+")
_wsere = re.compile(r"[ \t\n]+$")
def _stripws(s, atend=False):
    if s is None:
        return None
    return _wsere.sub("", s) if atend else _wssre.sub("", s)

def cleanup(node, parent=None):
    if node.tag == 'para':
        # cleanup specials and spaces
        i = -1
        if len(node) and node[i].tag == 'verse' and node[i].get('eid', None) is not None:
            i -= 1
        node.text = _stripws(node.text)
        if len(node) >= -i:
            if node[i].tail is not None:
                node[i].tail = _stripws(node[i].tail, atend=True)
                node[i].tail = add_specials(node[i].tail, node, parent)
        elif node.text is not None:
            node.text = _stripws(node.text, atend=True)
            node.text = add_specials(node.text, node, parent, istext=True)
    elif node.tag in ('chapter', 'verse'):
        node.text = None
    elif node.tag == "figure":
        fig2 = node.get("_unknown_", None)      # convert USFM2 to USFM3
        if fig2 is not None:
            bits = fig2.split("|")      # \fig_DESC|FILE|SIZE|LOC|COPY|CAP|REF\fig*
            if node.text is not None and len(node.text):
                node.set("alt", node.text.strip(WS))
            for i, a in enumerate(("src", "size", "loc", "copy", "caption", "ref")):
                if i < len(bits) and len(bits[i]):
                    node.set(a, bits[i].strip(WS))
            del node.attrib["_unknown_"]
        src = node.get("src", None)
        if src is not None:
            del node.attrib['src']
            node.set('file', src)
    elif node.tag == "cell":
        s = node.get("style", "")
        if "-" in s:
            start, end = s.split("-")
            startn = int(re.sub(r"^\D+", "", start))
            endn = int(end)
            span = endn - startn + 1
            node.set("colspan", str(span))
            node.set("style", start)
        celltype = re.sub(r"^t(.*?)\d.*$", r"\1", s)
        node.set("align", alignments.get(celltype, "start"))
    elif node.tag == "char":
        if node.get('style', '') == "xt" and ('href' in node.attrib or 'link-href' in node.attrib) \
                and (len(node) != 1 or node.text is not None or node[0].tag != 'ref'):
            refnode = node.__class__('ref', attrib=dict(loc=node.get('href', node.get('link-href', '')), gen="true"))
            refnode.text = node.text
            refnode[:] = node[:]
            node[:] = [refnode]
            node.text = None
            node = refnode
    for k, v in node.attrib.items():
        node.attrib[k] = re.sub(r"\\(.)", r"\1", v)
    for c in node:
        cleanup(c, parent=node)

_attribre = re.compile(r'(["=|\\~/])')
_textre = re.compile(r'([=|\\~/])')

def protect(txt, noquote=False):
    if txt is not None:
        return (_textre if noquote else _attribre).sub(r'\\\1', txt)
    return None

unescapes = {
    "&amp;": '&',
    "&lt;": '<',
    "&gt;": '>',
    "&quot;": '"',      #'
    "&apos;": "'"
}

def strnormal(s, t, mode=0):
    ''' strips whitespace according to element type and mode:
        mode & 1 strips lhs
        mode & 2 strips rhs
    '''
    if s is None:
        return ""
    res = re.sub("[\n\t\r ]+", " ", s) if t in ('para', 'char') else s
    if mode & 1 == 1:
        res = res.lstrip(WS)
    if mode & 2 == 2:
        res = res.rstrip(WS)
    res = re.sub(r"[ \n]*\n[ ]*", "\n", res)
    for k, v in unescapes.items():
        if k in res:
            res = res.replace(k, v)
    return res

notechars = [
    "fr ft fk fqa fq fl fw fdc fp".split(),
    "xt xop xo xta xk xq xot xnt xdc".split()]

def canonicalise(node, endofpara=False, factory=et, version=None):
    if version is None:
        version = node.get("version", "3.0")
    # whitespace and recursion
    if node.text is not None:
        mode = 1 # if len(node) else 3
        node.text = strnormal(node.text, node.tag, mode)
    lasti = 0
    for lasti, e in enumerate(reversed(node)):
        if e.tag not in ('char', 'note'):
            break
    lasti = len(node) - 1 - lasti
    for i, c in enumerate(node):
        eop = c.tag == 'para' or (endofpara and (i == lasti) and not c.tail)
        canonicalise(c, endofpara=eop, version=version)
        if c.tail is not None:
            mode = 2 if eop or c.tag in ("para", "sidebar") else 0
            c.tail = strnormal(c.tail, c.tag, mode)
    if node.tag == "note":
        # ensure text directly in a note ends up in an ft or xt
        style = node.get("style", "")
        replace = "xt" if style in ("x", "ex") else "ft"
        if node.text is not None:
            ft = node.makeelement("char", {"style": replace})
            ft.text = node.text
            node.text = None
            node.insert(0, ft)
        inserted = 0
        for i, c in enumerate(list(node)):
            if c.tail is not None:
                ft = node.makeelement("char", {"style": replace})
                node.insert(i + inserted + 1, ft)
                inserted += 1
                ft.text = c.tail
                c.tail = None
        for i, c in enumerate(list(node)):
            if c.get('style', '') not in notechars[0 if replace == "ft" else 1]:
                if len(node) == 1:
                    ft = node.makeelement("char", {"style": replace})
                    ft.append(c)
                    c.parent = ft
                elif i == 0:
                    node[1].insert(0, c)
                else:
                    node[i-1].append(c)
                node.remove(c)
                break
    if [int(x) for x in version.split(".")] >= [3, 1] and node.tag == "char" and node.get("style", "") == "xt" \
                and len(node) == 1 and isempty(node.text) and isempty(node[0].tail) and node[0].tag == "ref":
        i = node.parent.index(node)
        node.parent.insert(i, node[0])
        node[0].parent = node.parent
        node[0].attrib.pop("gen", "")
        node[0].tail = node.tail
        node.parent.remove(node)

def attribnorm(d):
    banned = ('closed', 'status', 'vid', 'version')
    return {k: strnormal(v, None) for k, v in d.items() if k not in banned and not k.startswith(" ") and v is not None and len(v)}

def listWithoutChapterVerseEnds(node):
    nodeList = []
    for child in node:
        if (child.tag != "verse" and child.tag != "chapter") or child.get("eid") is None:
            nodeList.append(child)
    return nodeList

def etCmp(a, b, at=None, bt=None, verbose=False, endofpara=False):
    """ Compares two nodes for debug purposes """
    aattrib = attribnorm(a.attrib)
    battrib = attribnorm(b.attrib)
    if a.tag != b.tag or aattrib != battrib:
        if verbose:
            print("tag or attribute: ", a, aattrib, b, battrib)
        return False
    mode = 1 if len(a) else 3
    if strnormal(a.text, a.tag, mode) != strnormal(b.text, b.tag, mode):
        if verbose:
            print("text or tag: ", a.text, a.tag, b.text, b.tag)
        return False
    lista = listWithoutChapterVerseEnds(a)
    listb = listWithoutChapterVerseEnds(b)
    if len(lista) != len(listb):
        if verbose:
            print("length mismatch: ", len(lista), len(listb))
            commonIndex = min(len(lista), len(listb)) - 1
            if commonIndex >= 0:
                print(f'item {commonIndex} in a: {lista[commonIndex]}')
                print(f'item {commonIndex} in b: {listb[commonIndex]}')
            if len(lista) > len(listb):
                print("first item in a not in b: ", lista[len(listb)])
            else:
                print("first item in b not in a: ", listb[len(lista)])
        return False
    lasti = 0
    for lasti, e in enumerate(reversed(lista)):
        if e.tag not in ('char', 'note'):
            break
    lasti = len(lista) - 1 - lasti
    for i, (ac, bc) in enumerate(zip(lista, listb)):
        act = a.tag if a is not None else None
        bct = b.tag if b is not None else None
        eop = a.tag == 'para' or endofpara and (i == lasti) 
        if not etCmp(ac, bc, act, bct, verbose=verbose, endofpara=eop):
            if verbose:
                print("child mismatch {}, {} [{}]: ".format(str(ac), str(bc), i))
            return False
        mode = 2 if eop or a.tag != "char" else 0
        if strnormal(ac.tail, act, mode) != strnormal(bc.tail, bct, mode):
            if verbose:
                print("tail or attributes: \"{}\", \"{}\" (at end of para={})".format(strnormal(ac.tail, act, mode), strnormal(bc.tail, bct, mode), str(eop)))
            return False
    return True


def iterusx(root, parindex=0, start=None, until=None, untilafter=False, blocks=[], unblocks=False, filt=[], grammar=None):
    """ Iterates over root yielding a node and whether we are in or after (isin) the node. Once until is hit,
        iteration stops. The node matching until is entered if untilafter is True
        otherwise it is not yielded.  blocks prunes any node whose
        style has a category listed in blocks. The test is inverted if unblocks is True.
        filt is a list of functions that all must pass for the value to be yielded.
        until may be a function that tests a node for it being the last node. """
    def makefn(b):
        if b is None:
            return lambda e: False
        elif callable(b):
            return b
        else:
            return lambda e: e == b

    if not len(filt):
        def test(e, isin):
            return True
    else:
        def test(e, isin):
            for f in filt:
                if not f(e, isin):
                    return False
            return True
    if len(blocks) and grammar is None:
        grammar = Grammar()

    untilfn = makefn(until)
    startfn = makefn(start)

    def category(s):
        s = grammar.parsetag(s)
        return grammar.marker_categories.get(s, "")

    def runiter(root, parindex=None, started=True):
        juststarted = False
        if parindex is None:
            if not started and startfn(root):
                started = True
                juststarted = True
            if started:
                if not juststarted and not untilafter and untilfn(root):
                    return (started, True)
                elif test(root, True):
                    yield root, True
        roots = list(root) if parindex is None else root[parindex:]
        finished = False
        for c in roots:
            if not len(blocks) or ((category(c.get('style', '')) in blocks) ^ (not unblocks)):
                started, finished = yield from runiter(c, started=started)
            if finished or (started and untilafter and untilfn(c)):
                return (started, True)
            if started and test(c, False):
                yield c, False
        return (started, False)

    yield from runiter(root, parindex=parindex, started=start is None)

def _sectionref(el, cref, grammar):
    start = el.parent.index(el)
    l = len(el.parent)
    cref.mrkrs = [MarkerRef(el.get("style", ""), 0, 1)]
    for i in range(start+1, l):
        p = el.parent[i]
        if p.tag != 'para':
            continue
        s = p.get("style", "")
        if grammar.marker_categories.get(s, "") != "versepara":
            continue
        if not isempty(p.text) or not len(p):
            return cref
        v = p[0]
        if v.tag != "verse":
            return cref
        cref.verse = int(v.get("number", 0))
        cref.word = None
        cref.char = None
        return cref
    return cref

def _wlen(t, w, c, atfirst=False):
    w = w or 0
    c = c or 0
    win = w
    cin = c
    b = re.split("([\u0020\n\u00a0\u1680\u2000-\u200b\u202f\u205f\u3000]+)", t)
    bin = b[:]
    if not len(b[0]):
        if w > 0 and c > 0:
            w += 1
            c = 0
        b = b[2:]
    elif w == 0:
        w = 1
    elif atfirst and c > 0:
        w += 1
        c = 0

    if len(b) and not len(b[-1]):
        b = b[:-2]
        finalspace = True
    else:
        finalspace = False

    if len(b):
        wc = (len(b) + 1) // 2
        cc = len(b[-1])
        if finalspace:
            w += wc
            c = 0
        else:
            w += wc - 1
            c = cc + (0 if wc > 1 else c)
    if w < win or w == win and c < cin:
        print(f"{win}+{cin} {bin} ({atfirst=}) -> {w},{c} {b=}")
    return (w, c)

def _extendlen(curr, txt, atfirst=False):
    if txt is not None and len(txt):
        # sc = str(curr)
        w, c = _wlen(txt, curr.getword(), curr.getchar(), atfirst=atfirst)
        curr.setword(w)
        curr.setchar(c)
        # print(f"{sc} -> {curr}")

def iterusxref(root, startref=None, book=None, grammar=None, skiptest=None, **kw):
    """ Iterates root as per iterusx yielding a RefRange that expresses the start
        and end of the text (text or tail) for the eloc. Yields eloc, ref """ 
    if grammar is None:
        grammar = Grammar()
    if startref is None:
        startref = Ref(book=book, chapter=0, verse=0, word=0, char=0)
        prev = root.getprevious_sibling()
        while prev is not None:
            if prev.tag == "verse" and startref.verse is None:
                startref.verse = prev.get("number", "")
                prev = prev.parent  # go up to the paragraph
            elif prev.tag == "chapter":
                startref.chapter = prev.get("number", "")
                break
            prev = prev.getprevious_sibling()
    lastref = startref
    atfirst = True
    notestack = []
    pcounts = {}
    for eloc, isin in iterusx(root, grammar=grammar, **kw):
        if isin:
            if eloc.tag in ("verse", "chapter"):
                curr = lastref.last.copy()
                setattr(curr, eloc.tag, int(eloc.get("number", 0)))
                curr.word = 0
                curr.char = 0
                curr.mrkrs = None
                pcounts = {}
            elif eloc.tag == "note" and eloc != kw.get('start', None):
                notestack.append(lastref.last)
                curr = lastref.last.copy()
                if curr.mrkrs is None:
                    curr.mrkrs = []
                curr.mrkrs.append(MarkerRef(eloc.get("style", ""), 0, 0))
                curr.word = None
                curr.char = None
            else:
                curr = None
            if eloc.tag in ("para", ):
                # deal with section heads and lookahead for the reference
                s = eloc.get("style", "")
                pcounts[s] = pcounts.get(s, 0) + 1
                if grammar.marker_categories.get(s, "") == "sectionpara":
                    lastref = _sectionref(eloc, lastref.last.copy(), grammar)
                atfirst = True
                if lastref.last.getchar() > 0:
                    lastref = RefRange(lastref.first, lastref.last.copy())
                    lastref.last.setword(lastref.last.getword() + 1)
                    lastref.last.setchar(0)
                if lastref.mrkrs and len(lastref.mrkrs) and lastref.mrkrs[0].mrkr in pcounts:
                    lastref.mrkrs[0].mrkr = s
                    lastref.mrkrs[0].index = pcounts[s]
                else:
                    lastref.mrkrs = [MarkerRef(s, pcounts[s], 1)]
                    lastref.word = None
                    lastref.char = None
            if eloc.text is not None and len(eloc.text):
                if curr is None:
                    curr = lastref.last.copy()
                if curr.getchar() > 0 and (skiptest is None or not skiptest(eloc.getnext())):
                    w = curr.getword()
                    curr.setword(w + 1)
                    curr.setchar(0)
                _extendlen(curr, eloc.text, atfirst=True)
                cref = RefRange(lastref.last, curr)
            elif curr is not None:
                cref = RefRange(lastref.last, curr)
            else:
                cref = lastref.last
        else:
            if eloc.tag == "note":
                if not len(notestack):
                    return
                curr = notestack.pop().copy()
            elif eloc.tag == "para":
                curr = lastref.last.copy()
                curr.mrkrs = []
            else:
                curr = lastref.last.copy()
            if eloc.tail is not None and len(eloc.tail):
                natfirst = skiptest is not None and skiptest(eloc)
                _extendlen(curr, eloc.tail, atfirst=not natfirst)
                cref = RefRange(lastref.last, curr)
            else:
                cref = curr
        yield (eloc, isin, cref)
        lastref = cref

def vnumin(s, v, base):
    b = base.copy()
    b.verse = None
    b.subverse = None
    b.word = None
    b.char = None
    b.mrkrs = None
    r = Ref(str(b)+":"+s)
    if v >= r.first.verse and v <= r.last.verse:
        return True

def _addoblink(res, cref, tid, ttype):
    k = (tid, ttype)
    r = cref.copy()
    if k in res:
        oldr = res[k]
        if oldr.first != oldr.last:
            oldr.last = r
        elif oldr.last == r:
            if r.getchar(None) is not None and oldr.first.getchar(None) is None:
                oldr.first.setchar(1)
                res[k] = RefRange(oldr.first, r)
        else:
            try:
                res[k] = RefRange(oldr.first, r)
            except ValueError:
                pass
    else:
        res[k] = r

def getlinkages(usx):
    res = {}
    for eloc, isin, cref in iterusxref(usx.getroot(), book=usx.book, skiptest=lambda e:e.tag=="ms" and e.get("style","").startswith("za")):
        if not isin:
            s = eloc.get("style", "")
            if eloc.tag == "ms" and s.startswith("za"):
                i = eloc.parent.index(eloc)
                lref = cref.first.copy()
                key = (eloc.get("aid", ""), eloc.get("type", "unk"))
                # spot word spans
                if s == "za-s" and cref.first.getchar() == 0:
                    lref.setchar(None)
                elif s == "za-e" and (not eloc.tail or eloc.tail[0] in \
                            "\u0020\n\u00a0\u1680\u2000-\u200b\u202f\u205f\u3000") \
                        and (key not in res or res[key].getchar(None) is None):
                    lref.setchar(None)
                _addoblink(res, lref, *key)
                if i == 0:
                    if eloc.parent.text is None:
                        eloc.parent.text = eloc.tail
                    elif eloc.tail is not None:
                        eloc.parent.text += eloc.tail
                elif eloc.parent[i-1].tail is None:
                    eloc.parent[i-1].tail = eloc.tail
                elif eloc.tail is not None:
                    eloc.parent[i-1].tail += eloc.tail
                eloc.parent.remove(eloc)
    return res

def insertlinkages(usx, links):
    ''' links = [(ref, mrkr, atend, id, type)] '''
    from usfmtc.usxcursor import USXCursor
    for l in links:
        loc = USXCursor.fromRef(l[0], usx, atend=l[2], skiptest=lambda e:e.tag=="ms" and e.get("style","").startswith("za"))
        _insertoblink(loc, l[1], l)

def _insertoblink(linkloc, tag, linfo):
    el = linkloc.el
    newel = el.makeelement("ms", {"style": tag, "aid": linfo[3]})
    if linfo[4] != "unk":
        newel.set("type", linfo[4])
    if linkloc.attrib == " text":
        newel.tail = el.text[linkloc.char:]
        el.text = el.text[:linkloc.char]
        el.insert(0, newel)
    else:   # tail
        newel.tail = el.tail[linkloc.char:]
        el.tail = el.tail[:linkloc.char]
        newel.parent = el.parent
        el.parent.insert(el.parent.index(el)+1, newel)

def _getref(e, book, lastchap=0):
    refstr = e.get("sid", None)
    if refstr is None:
        num = int(e.get("number", 0))
        if e.tag == "verse":
            ref = Ref(book=book, chapter=lastchap, verse=num)
        else:
            ref = Ref(book=book, chapter=num, verse=0)
    else:
        ref = Ref(refstr)
    return ref


def reversify(usx, srcvrs, tgtvrs):
    """ Convert the versification of the text from one system to another limted
        to the changes being monotonically increasing, that is no reordering """
    def isptype(e, s):
        return e.tag == "para" and usx.grammar.marker_categories.get(e.get("style", ""), None) == s

    bk = usx.book
    curr = Ref(None)
    lastref = Ref(None)
    removecs = []
    insertcs = []
    root = usx.getroot()
    rootlist = list(root)
    synco = 0
    chapters = [0] + [i for i, e in enumerate(rootlist) if e.tag=="chapter"]
    for i, pe in enumerate(rootlist):
        if pe.tag == "chapter":
            ref = _getref(pe, bk)
            if ref is None:
                continue
            oref = srcvrs.remap(ref, tgtvrs)
            chapters[oref.chapter] += synco
            if oref == ref and ref >= curr or oref.chapter != ref.chapter:
                if oref.verse > 0:
                    # insert verse at start of next versepara
                    for se in rootlist[i+1:]:
                        if isptype(se, "versepara"):
                            newv = se.makeelement("verse", {"style": "v", "number": str(oref.verse), "ssid": str(oref)})
                            newv = se.text
                            se.text = None
                            se.insert(0, newv)
                            break
                    else:
                        raise ValueError(f"Can't insert verse for {oref} at chapter {ref.chapter}")
                if oref.chapter != ref.chapter:
                    pe.set("number", str(oref.chapter))
                lastref, curr = ref, oref
                continue
            root.remove(pe)
            synco -= 1
            lastref, curr = ref, oref
            continue
        for ve in pe:
            if ve.tag != "verse":
                continue
            ref = _getref(ve, bk, lastchap=lastref.chapter or 0)
            if ref is None:
                continue
            oref = srcvrs.remap(ref, tgtvrs)
            if oref == ref or oref.verse == 0:
                if oref.verse == 0:
                    pe.remove(ve)
                lastref, curr = ref, oref
                continue
            if oref.chapter != curr.chapter:
                # insert chapter above section paras
                for j, se in enumerate(rootlist[i-1:0:-1]):
                    if isptype(se, "sectionpara"):
                        continue
                    if se.tag != "chapter":
                        newc = root.makeelement("chapter", {"style": "c", "number": str(oref.chapter)}, pos=ve.pos)
                        root.insert(i + synco - j, newc)
                        synco += 1
                        if i + synco - j != root[chapters[oref.chapter]]:
                            while isptype(ce := root[chapters[oref.chapter]+1], "sectionpara"):
                                root.remove(ce)
                                root.insert(i + synco - j, ce)
                    break
            if oref.verse != ref.verse or oref.subverse != ref.subverse:
                ve.set("number", str(oref.verse))
                ve.set("ssid", str(oref))
            lastref, curr = ref, oref

