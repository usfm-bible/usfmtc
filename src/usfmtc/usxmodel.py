
import re
from dataclasses import dataclass
from usfmtc.xmlutils import isempty
from usfmtc.usfmparser import Grammar
from usfmtc.reference import Ref
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
                or (not len(lastp) and (lastp.text is None or lastp.text.strip() == "")):
            pending.append(lastp)
        elif id(lastp) != id(endp) or atend or endp[0].tag != "verse" or (endp.text is not None and endp.text.strip() != ""):
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

def addesids(root):
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
    for v in list(root.iter()):
        if v.tag == "chapter":
            currchap = v.get('number')
            currverse = 0
            v.set('sid', "{} {}".format(bk, currchap))
            continue
        elif v.tag == "para":
            lastp = v
            continue
        elif v.tag != "verse" or v.get('eid', None) is not None:
            continue
        currverse = v.get('number')
        v.set('sid', "{} {}:{}".format(bk, currchap, currverse))
        if lastv is None:
            lastv = v
            continue
        eid = lastv.get('sid', None)
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
                node.set("alt", node.text.strip())
            for i, a in enumerate(("src", "size", "loc", "copy", "caption", "ref")):
                if i < len(bits) and len(bits[i]):
                    node.set(a, bits[i].strip())
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
            refnode = et.Element('ref', loc=node.get('href', node.get('link-href', '')), gen="true")
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

def messup(node, parent=None):
    ''' Opposite of cleanup, to prepare a USX XML structure for USFM generation.
        Returns a copy of the structure so as not to polute the core data. '''
    if parent is None:
        newnode = et.Element(node.tag, attrib=node.attrib)
    else:
        newnode = et.SubElement(parent, node.tag, attrib=node.attrib)
    newnode.text = node.text
    newnode.tail = node.tail

    if newnode.tag == "figure":
        src = newnode.get("file", None)
        if src is not None:
            del newnode.attrib['file']
            newnode.set('src', src)
    elif newnode.tag == "cell":
        tag = newnode.get("style", "")
        span = int(newnode.get("colspan", "1"))
        if span > 1:
            start = int(re.sub(r"^\D+", "", tag))
            tag = tag + "-" + str(start + span - 1)
            newnode.set("style", tag)
    # convert \xt\ref Genesis 1:1|loc="GEN 1:1"\ref*|link-href="GEN 1:1"\xt*
    # back to \xt Genesis 1:1|link-href="GEN 1:1"\xt*
#    elif newnode.tag == "char" and node.get('style', '').endswith('xt') and not newnode.text and len(node) == 1:
#        c = node[0]
#        if c.tag == "ref" and not c.tail:
#            newnode.text = protect(c.text)
#            return newnode
    for c in node:
        messup(c, parent=newnode)
    return newnode


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
        res = res.lstrip(" \t\n\r")
    if mode & 2 == 2:
        res = res.rstrip(" \t\n\r")
    res = re.sub(r"[ \n]*\n[ ]*", "\n", res)
    for k, v in unescapes.items():
        if k in res:
            res = res.replace(k, v)
    return res

notechars = [
    "fr ft fk fqa fq fl fw fdc fp".split(),
    "xt xop xo xta xk xq xot xnt xdc".split()]

def canonicalise(node, endofpara=False, factory=et):
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
        canonicalise(c, endofpara=eop)
        if c.tail is not None:
            mode = 2 if eop or c.tag in ("para", "sidebar") else 0
            c.tail = strnormal(c.tail, c.tag, mode)
    if node.tag == "note":
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


@dataclass(slots=True, eq=False)
class Xmlloc:
    parent: et.Element
    head:   et.Element

def iterusx(root, parindex=0, start=None, blocks=[], filt=[], unblocks=False, grammar=None, until=None):
    """ Iterates over root yielding an Xmlloc for each node. Once until is hit,
        iteration stops (after yielding the until). blocks prunes any node whose
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
        def test(e):
            return True
    else:
        def test(e):
            for f in filt:
                if not f(e):
                    return False
            return True
    if len(blocks) and grammar is None:
        grammar = Grammar()

    untilfn = makefn(until)
    startfn = makefn(start)

    _catre = re.compile(r"[_^].*$")
    def category(s):
        s = _catre.sub("", s)
        return grammar.marker_categories.get(s, "")

    def runiter(root, parindex=None, started=True):
        if parindex is None:
            this = Xmlloc(root, None)
            if not started and startfn(root):
                started = True
            if started and test(this):
                yield this
            if untilfn(root):
                return (started, True)
        roots = list(root) if parindex is None else root[parindex:]
        finished = False
        for c in roots:
            if not len(blocks) or ((category(c.get('style', '')) in blocks) ^ (not unblocks)):
                started, finished = yield from runiter(c, started=started)
            if finished:
                return (started, True)
            this = Xmlloc(root, c)
            if started and test(this):
                yield this
            if untilfn(c):
                return (started, True)
        return (started, False)

    yield from runiter(root, parindex=parindex, started=start is None)

def copy_range(root, a, b):
    ''' Returns a usx document containing paragraphs containing the content
        between a and b '''
    factory = root.__class__
    if a.el not in root:
        p = a.el.parent
        while p not in root:
            p = p.parent
    else:
        p = a.el
    i = list(root).index(p)
    allnew = {}
    res = factory(root.tag, attrib=root.attrib)
    currp = res
    curr = root
    for eloc in iterusx(root, parindex=i, start=a.el, until=b.el):
        if eloc.head is None and eloc.parent == b.el:
            break
        elif curr is root and eloc.head is None and eloc.parent.tag not in ("para", "book", "sidebar"):
            newp = factory(eloc.parent.parent.tag, attrib=eloc.parent.parent.attrib, parent=currp)
            if 'vid' not in eloc.parent.parent.attrib and 'vid' in eloc.parent.attrib:
                newp.set('vid', eloc.parent.get('vid', ''))
            currp.append(newp)
            currp = newp
            curr is eloc.parent.parent
        if eloc.head is None:
            newp = factory(eloc.parent.tag, attrib=eloc.parent.attrib, parent=currp)
            newp.text = eloc.parent.text
            currp.append(newp)
            currp = newp
            curr = eloc.parent
        elif eloc.head == curr:
            currp.tail = eloc.head.tail
            currp = currp.parent
            curr = curr.parent if curr is not None else root
        else:
            pass
    if len(res):    # strip final empty paragraph (that probably starts with the ending verse)
        last = res[-1]
        if last.tag in ("para", "book", "sidebar") and not len(last) and isempty(last.text):
            res.remove(last)
    return res

def copy_text(root, a, b):
    ''' Returns a text string of all the main text between a and b '''
    res = []
    if a.el not in root:
        p = a.el.parent
        while p not in root:
            p = p.parent
    else:
        p = a.el
    i = list(root).index(p)
    for eloc in iterusx(root, parindex=i, start=a.el, until=b.el):
        if eloc.head is None:
            if not isempty(eloc.parent.text):
                start = 0; end = len(eloc.parent.text)
                if eloc.parent == a.el:
                    if a.attrib == " text":
                        start = a.char
                if eloc.parent == b.el:
                    if b.attrib == " text":
                        end = b.char
                res.append(eloc.parent.text[start:end])
        elif eloc.head == a.el and a.attrib == " tail":
            res.append(eloc.head.tail[a.char:])
        elif eloc.head == b.el and b.attrib == " text":
            pass
        elif not isempty(eloc.head.tail):
            res.append(eloc.head.tail)
    if not len(res) and a.attrib == " tail":
        start = a.char
    else:
        start = 0
    if b.attrib == " tail":
        res.append(b.el.tail[start:b.char])
    return "".join(res)
    

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

@dataclass
class USXLoc:
    el: et.Element
    attrib: str     # " text", " tail". Where the .char indexes into
    char: int       

def _findel(node, tag, attrib, limits=[]):
    """ Search for an element with the given tag and attrib matching forwards from
        node, including down into children. Returns a node. Limits is a list of stop
        tags that cause the search to fail, returning None. """
    for eloc in iterusx(node, until=lambda e: e.tag in limits):
        if eloc.head is not None or eloc.parent.tag != tag:
            continue
        for k, v in attrib.items():
            if eloc.parent.get(k, None) != v:
                break
        else:
            return eloc.parent 

def _findtext(node, limits):
    """ Iterator returning text strings until an element in limits is encountered """
    if not isempty(node.text):
        yield(node.text, node, " text")
    for eloc in iterusx(node, until=lambda e: e.tag in limits):
        if eloc.head is None:
            if not isempty(eloc.parent.text):
                yield (eloc.parent.text, eloc.parent, " text")
        elif not isempty(eloc.head.tail):
            yield (eloc.head.tail, eloc.head, " tail")
    if not isempty(node.tail):  # but what if we hit the limits?
        yield(node.tail, node, " tail")

def _findcvel(ref, root, grammar, atend=False, parindex=0):
    if ref.book:
        bkel = root.find("./book")
        bk = bkel.get("code", "")
        if ref.book is not None and bk != ref.book:
            raise ValueError("Reference book {} != text book {}".format(ref, bk))
    c = ref.chapter
    foundend = False
    if c is not None and c > 0:
        for pari, el in enumerate(root[parindex:], start=parindex):
            if el.tag == "chapter" and int(el.get('number', 0)) == c:
                parindex = pari
                if atend and not foundend:
                    startparindex = pari
                    c += 1
                    foundend = True
                else:
                    break
        else:
            if not atend:
                raise ValueError("Chapter reference {} out of range".format(ref))
            else:
                parindex = len(root)
    v = ref.verse
    if v is not None and v > 0:
        if atend:
            parindex = startparindex + 1
            if not ref.mrkrs and not ref.word and not ref.char:
                v += 1
        else:
            parindex += 1
        while parindex < len(root):
            n = root[parindex]
            el = _findel(n,  "verse", {"number": str(v)}, limits=("chapter",))
            if el is not None:
                break
            parindex += 1
        else:
            raise ValueError("Reference verse {} out of range".format(ref))
    if ref.mrkrs:
        if not ref.word and not ref.char:
            oparindex = parindex
            t = ref.mrkrs[0].mrkr   # look forward or backwards for a para
            if grammar.marker_categories.get(t, "") in ("sectionpara",):
                while parindex > 0:
                    p = root[parindex]
                    if p.get("style", "") == t:
                        if ref.mrkrs[0].index is None or ref.mrkrs[0].index - 1 == count:
                            foundme = True
                            break
                    parindex -= 1
                    endme = False
                    for e in root[parindex]:
                        if e.tag == "verse" and not vnumin(e.get("number", ""), v, ref.last if atend else ref.first):
                            endme = True
                            break
                    if endme:
                        parindex = oparindex
                        raise SyntaxError("Cannot find preceding section paragraph {t} in {ref}")
                    else:
                        el = root[parindex]
            else:
                for eloc in iterusx(root, parindex=parindex, start=lambda e:e.tag == "verse" and vnumin(e.get("number", ""), v, ref.last if atend else ref.first), until=lambda e:e.tag == "verse" and not vnumin(e.get("number", ""), v, ref.last if atend else ref.first)):
                    if eloc.head is not None:
                        continue
                    if eloc.parent.get("style", "") == t:
                        el = eloc.parent
                        break
    return el

def _findtextref(ref, el, atend=False, mrkri=0):
    if mrkri > 0:
        r = ref.mrkrs[mrkri-1]
    else:
        r = ref
    a = ""
    w = -1
    c = -1
    clen = -1
    t = ""
    if r.word is None or r.word == 0:
        t = el.get('number', "")
        a = "number"
        c = 0
        clen = len(t)
    else:
        word = r.word - 1
        for t, el, a in _findtext(el, limits=("chapter", "verse")):
            b = re.split("([\u0020\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000]+)", t)
            if not len(b[-1]):
                b.pop()
            if not len(b[0]):
                b.pop(0)
                b.pop(0)
            l = (len(b) + 1) // 2
            if not len(b[0]):
                l -= 1
            if l < word:
                word -= l
                continue
            c = sum(len(s) for s in b[:word*2])
            clen = len(b[word*2])
            if ref.mrkrs and len(ref.mrkrs) > mrkri and c + clen == len(t.rstrip()):
                en = el.getnext()
                while en is not None:
                    if en.get("style", "") == ref.mrkrs[mrkri].mrkr:
                        break
                else:
                    raise SyntaxError(f"Can't find {ref.mrkrs[mrkri+1].mrkr}")
                return _findtext(ref, en, atend=atend, mrkri=mrkri+1)
            break
        else:
            raise ValueError("Reference word {} out of range".format(ref))
    if r.char is not None:
        if r.char > clen:
            raise ValueError("Reference char {} out of range for word length {}".format(ref, clen))
        c += r.char
    elif atend:
        c += clen
    return USXLoc(el, a, c)

def findref(ref, root, atend=False, parindex=0, grammar=None):
    """ From a reference, return a USXLoc (element, attribute and char index) """
    if grammar is None:
        grammar = Grammar()
    el = _findcvel(ref, root, grammar, atend=atend, parindex=parindex)
    if ref.word is not None or ref.char is not None:
        res = _findtextref(ref, el, atend=atend)
    elif ref.mrkrs:
        res = _findtextref(ref, el, atend=atend, mrkri=1)
    elif atend and len(el):
        res = USXLoc(el[-1], " tail", -1)
    else:
        res = USXLoc(el, " text", -1 if atend else 0)
    # What about markers?
    return res

