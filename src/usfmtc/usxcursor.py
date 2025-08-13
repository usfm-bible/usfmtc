
from usfmtc.usxmodel import iterusx, iterusxref
from usfmtc.xmlutils import isempty
from usfmtc.reference import MarkerRef
from dataclasses import dataclass
import xml.etree.ElementTree as et
from typing import Optional
import re

@dataclass
class ETCursor:
    el: et.Element
    attrib: str | bool
    char: int

    def istail(self):
        ''' Are we referencing the tail text of the element? '''
        return self.attrib == " tail"

    def istext(self):
        ''' Are we referencing the text in the element? '''
        return self.attrib == " text"

    def text(self, el):
        ''' Returns the textual element of el of self, ignoring char '''
        if self.istext():
            return self.el.text
        elif self.istail():
            return self.el.tail
        elif (v := self.el.get(self.attrib, None)) is not None:
            return v
        return None

    def textin(self, other, eloc, isin):
        ''' Returns the text between self and other (exclusive) given whether
            the text is in or after element eloc '''
        if not self.attrib.startswith(" "):
            t = eloc.get(self.attrib, "")
            start = self.char
            end = len(t)
            if other.attrib == self.attrib:
                end = other.char
            return t[start:end]
        t = eloc.text if isin else eloc.tail
        start = 0; end = len(t) if t else 0
        if eloc == self.el and self.istext() == isin:
            start = self.char
        if eloc == other.el and other.istext() == isin:
            end = other.char
        return t[start:end] if t else t


def testverse(v:str, verse:str) -> bool:
    if v == verse:
        return True     # short circuit
    if "-" not in verse and "," not in verse:
        return False
    b = verse.split(",")        # list of ranges
    if len(b) > 1:
        return any(testverse(v, ab) for ab in b)
    b = verse.split("-")        # range, just take ends
    if len(b) > 1:
        try:
            bi = int(b[0])
            ba = int(b[-1])
            t = int(v)
            return t >= bi and t <= ba
        except ValueError:
            return False

def vint(v:str|int) -> int:
    if isinstance(v, int):
        return v
    while len(v):
        try:
            return int(v)
        except ValueError:
            pass
        v = v[:-1]
    return None

def _findel(node, tag, attrib, limits=[], parindex=None, count=None, start=None):
    """ Search for an element with the given tag and attrib matching forwards from
        node, including down into children. Returns a node. Limits is a list of stop
        tags that cause the search to fail, returning None. """
    testattrib = {k: (v if callable(v) else lambda a: a == v) for k, v in attrib.items()}
    for eloc, isin in iterusx(node, start=start, parindex=parindex, until=lambda e: e.tag in limits):
        if not isin or eloc.tag != tag:
            continue
        if all(fn(eloc.get(k, None)) for k, fn in testattrib.items()):
            if not count:
                return eloc
            count -= 1

def _scanel(refmrkr, usx, parindex, rend=None, verseonly=False):
    """ Returns element and parindex for a reference marker following the given parindex """
    pcounts = {}
    if rend is None:
        rend = len(usx.getroot()) 
    while parindex < rend:
        e = usx.getroot()[parindex]
        if e.tag == "chapter":      # bounded by CV
            return None, None
        s = e.get("style", "")
        pcounts[s] = pcounts.get(s, 0) + 1      # count paragraph indices by marker
        if s == refmrkr.mrkr and (not refmrkr.index or refmrkr.index == pcounts[s]):
            return e, parindex                  # found it
        if verseonly and usx.grammar.marker_categories.get(s, "") == "versepara":   # test for verse bound
            for v in e:
                if v.tag == "verse":
                    return None, None
        parindex += 1

def _findcvel(ref, usx, atend=False, parindex=0):
    ''' Returns an element and mrkr index for a reference in a document. If atend
        _findcvel will return the element containing the endpoint or if that is at
        the end of the elment, the next element. parindex speeds up the hunt for the
        chapter.'''
    resm = 0
    if ref.book:
        if ref.book is not None and usx.book != ref.book:
            raise ValueError("Reference book {} != text book {}".format(ref, usx.book))
    root = usx.getroot()
    c = ref.chapter
    foundend = False

    # find a parindex for the given chapter
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

    # scan for verse. Verses always have paragraphs as their parent
    if v is not None and v != "end" and vint(v) > 0:
        if atend:
            parindex = startparindex + 1
            if not ref.mrkrs and ref.word is None and ref.char is None:
                v += 1
        else:
            parindex += 1
        while parindex < len(root):
            n = root[parindex]
            if n.tag == "chapter":
                el = n
                break
            el = _findel(n, "verse", {"number": lambda n:testverse(str(v), n)}, limits=("chapter",))
            if el is not None:
                break
            parindex += 1
        else:
            if not atend:
                raise ValueError("Reference verse {} out of range".format(ref))
            else:
                return None, 0
    elif parindex >= len(root):
        return None, 0
    else:
        el = root[parindex]

    # found el for basic C:V now for any !markers at the verse level
    if ref.mrkrs and not ref.word and not ref.char:
        pcounts = {}
        curr = ref.last if atend else ref.first
        while resm < len(ref.mrkrs):
            if not curr.word and not curr.char:
                oparindex = parindex
                t = ref.mrkrs[resm].mrkr   # look forward or backwards for a para
                catt = usx.grammar.marker_categories.get(t, "")
                if catt == "sectionpara":       # we are looking for a sectionpara
                    parindex -= 1
                    while parindex > 0:         # scan backwards for start of sectionparas
                        el = root[parindex]
                        if el.tag == "para":
                            s = el.get("style", "")
                            if usx.grammar.marker_categories.get(s, "") != "sectionpara":
                                break
                        else:
                            break
                        parindex -= 1
                    # now scan forwards for given para
                    el, parindex = _scanel(ref.mrkrs[resm], usx, parindex+1, rend=oparindex)
                elif 'para' in catt or catt in ("introduction", "title"):   # introductions
                    el, parindex = _scanel(ref.mrkrs[resm], usx, parindex+1, verseonly=True)
                elif catt in ("footnote", "crossreference", "char") and ref.word is None and ref.char is None:  # a note
                    tag = {"footnote": "note", "crossreference": "note", "char": "char"}[catt]
                    el = _findel(root, tag, {"style": t}, limits=("verse", "chapter"), parindex=parindex, count=ref.mrkrs[resm].index, start=el)
                else:
                    break
                if el is None:
                    break
                curr = ref.mrkrs[resm]
                resm += 1
            else:
                break
    return el, resm

def _findtextref(ref, el, cls, atend=False, mrkri=-1, startref=None, skiptest=None):
    ''' Given an element containing the ref, searches within it for the word and char parts of
        a reference. ref can be a list of ref if mrkri==0. atend causes the return
        to be one past the last character of the reference. '''
    if el is None:
        return el
    if mrkri > 0:
        r = ref.mrkrs[mrkri-1]
    else:
        r = ref
    p = el.parent
    if p.parent is None:
        p = el
    pi = p.parent.index(p)
    res = None
    islast = False
    # iterate over elements telling us where we are with each one
    for (eloc, isin, cref) in iterusxref(p.parent, startref=startref, parindex=pi, start=el,
                                    until=lambda t:t != el and t.tag in ("chapter", "verse"),
                                    skiptest=skiptest):
        # does this element cover our reference?
        if cref.first.getword() > r.getword() or cref.last.getword(r.getword()) < r.getword():
            continue
        if (cref.first.getword() == r.getword() and cref.first.getchar() > r.getchar()) \
                or (cref.last.getword(r.getword()) == r.getword() and cref.last.getchar() < r.getchar()):
            continue
        if r.getchar(None) is None and cref.last.getword() == r.getword() and cref.last.getchar() == 0:
            continue 
        if isin:
            a = " text"
            t = eloc.text
            e = eloc
        else:
            a = " tail"
            t = eloc.tail
            e = eloc.parent
        if not t:
            continue
        # chop up words
        b = re.split("([\u0020\n\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000]+)", t)
        windex = r.getword() + 1 if not len(b[0]) and cref.first.getchar() == 0 else r.getword()
        windex = 2 * (windex - cref.first.getword(1)) + (1 if atend and r.getchar() == 0 else 0)
        # find char index for start of word and then offset within that
        w = sum(len(s) for s in b[:windex])
        c = r.getchar() - (cref.first.getchar() if r.getword() == cref.first.getword() else 0)
        # are we at the end of the text run and so can look for other markers?
        if windex == len(b):
            islast = True
        elif len(b) % 2 == 1:       # odd => no final space
            if windex == len(b) - 1 and (c == 0 or c == len(b[-1])):
                islast = True
        elif windex == len(b) - 1:
            islast = True
        res = cls(eloc, a, w+c)

        # look for a following marker if there are any
        if ref.mrkrs is not None and len(ref.mrkrs) > mrkri:
            m = ref.mrkrs[mrkri]
            if not islast:
                raise ValueError(f"{m.mrkr} not found in {ref}")
            # where to start search inside or in parent
            i = 0 if isin else eloc.parent.index(eloc) + 1
            while i < len(e):
                nel = e[i]
                if nel.get("style", "") == m.mrkr:
                    # hit. Recurse if there are more constraints
                    if mrkri < len(ref.mrkrs) or ref.mrkrs[mrkri].word or ref.mrkrs[mrkri].char:
                        sref = (cref.last if atend else cref.first).copy()
                        if sref.mrkrs is None:
                            sref.mrkrs = []
                        sref.mrkrs.append(MarkerRef(ref.mrkrs[mrkri].mrkr))
                        return _findtextref(ref, nel, cls, atend=atend, mrkri=mrkri+1, startref=sref)
                # if text between can't keep hunting
                if isempty(nel.tail):
                    i += 1
                else:
                    break
        return res


class USXCursor(ETCursor):

    @classmethod
    def fromRef(cls, ref, usx, atend=False, parindex=0, skiptest=None):
        ''' Returns a cursor for the given ref in the usx file. atend indicates
            that this is a final cursor, which is exclusive (so beyond the
            given ref). parindex speeds up the hunt by skipping paragraphs.
            skiptest is a function to say whether this element causes a word break. '''
        el, mrkri = _findcvel(ref, usx, atend=atend, parindex=parindex)
        if el is None:
            return cls(None, "", 0)
        elref = ref.copy()
        if elref.mrkrs and len(elref.mrkrs):
            elref.mrkrs = elref.mrkrs[:mrkri]
        if atend:
            elref.last.setword(None)
            elref.last.setchar(None)
        else:
            elref.first.setword(None)
            elref.first.setchar(None)
        word = ref.mrkrs[mrkri-1].word if mrkri > 0 else ref.word
        char = ref.mrkrs[mrkri-1].char if mrkri > 0 else ref.char
        if word is not None or char is not None:
            res = _findtextref(ref, el, cls, atend=atend, startref=elref, mrkri=mrkri, skiptest=skiptest)
        elif ref.mrkrs and len(ref.mrkrs) > mrkri:
            res = _findtextref(ref, el, cls, atend=atend, startref=elref, mrkri=mrkri+1, skiptest=skiptest)
        elif atend and len(el):
            res = cls(el[-1], " tail", -1)
        else:
            res = cls(el, " text", -1 if atend else 0)
        return res

    def copy_range(self, root, b, addintro=False, skiptest=None, titles=True, headers=True,
                                  chapters=True, vid=None, grammar=None, factory=None):
        ''' Returns a usx document root containing paragraphs containing the content
            up to but not including USXCursor b '''
        a = self
        if factory is None:
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
        if addintro or titles:
            categories = ["versepara", "sectionpara"] + ["title", "introduction"] if not addintro else []
            def isendintro(e):
                if e.tag == "chapter":
                    return True
                s = e.get("style", "")
                return grammar.marker_categories.get(s, "") in categories
            # copy the tree up to the first chapter or verse text
            for eloc in root:
                if isendintro(eloc):
                    break
                newp = eloc.copy(deep=True, parent=currp, factory=factory)
                currp.append(newp)
            curr = root
            currp = res

        for eloc, isin in iterusx(root, parindex=i, start=a.el, until=b.el, untilafter=bool(b.attrib)):
            if isin and eloc == b.el:
                break
            # at the start
            elif isin and eloc == a.el and eloc.tag not in ("para", "book", "sidebar"):
                # if we are at the start of the parent (para, since a verse is always only in a para) check for subheadings
                if headers and grammar and isempty(eloc.parent.text) and eloc.parent.index(eloc) == 0:  # are we first?
                    r = eloc.parent.parent  # should be root
                    i = r.index(eloc.parent) - 1
                    # scan back over section heads
                    while i > 0 and ((chapters and r[i].tag == "chapter") or \
                            (r[i].tag == "para" and grammar.marker_categories.get(r[i].get("style", None), "") == "sectionpara")):
                        i -= 1
                    i += 1
                    # copy all the section heads
                    for j in range(i, r.index(eloc.parent)):
                        newp = r[j].copy(deep=True, parent=currp, factory=factory)
                        currp.append(newp)
                outp = factory(eloc.parent.tag, attrib=eloc.parent.attrib, parent=currp)
                if 'vid' not in eloc.parent.attrib:
                    outp.set('vid', eloc.get('vid', vid.str() if vid is not None else ''))
                currp.append(outp)
                currp = outp
                curr = eloc

            # now always copy the element
            if isin:
                newp = factory(eloc.tag, attrib=eloc.attrib, parent=currp)
                newp.text = a.textin(b, eloc, isin)
                currp.append(newp)
                currp = newp
                curr = eloc
            # after the element so grab the tail and go up in the hierarchy
            elif eloc == curr:
                currp.tail = a.textin(b, eloc, isin)
                currp = currp.parent
                curr = curr.parent if curr is not None else root
            else:
                pass
        if len(res):    # strip final empty paragraph (that probably starts with the ending verse)
            last = res[-1]
            if last.tag in ("para", "book", "sidebar") and not len(last) and isempty(last.text):
                res.remove(last)
        for i in range(len(res) - 1, -1, -1):
            if res[i].tag == "para" and grammar.marker_categories.get(res[i].get("style", None), "") == "sectionpara":
                res.remove(res[i])
            else:
                break
        return res

    def copy_text(self, root, b):
        ''' Returns a text string of all the main text between self and b (exclusive)'''
        a = self
        res = []
        if a.el not in root:
            p = a.el.parent
            while p not in root:
                p = p.parent
        else:
            p = a.el
        i = list(root).index(p)
        for eloc, isin in iterusx(root, parindex=i, start=a.el, until=b.el, untilafter=bool(b.attrib)):
            t = a.textin(b, eloc, isin)
            if t:
                res.append(t)
        return "".join(res)

