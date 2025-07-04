#!/usr/bin/env python3

import regex
import xml.etree.ElementTree as et
from usfmtc.extension import SFMFile
from collections import UserDict, UserString

WS = "\t\n\r "   # \v\f\u001C\u001D\u001E\u001F "  full python ASCII WS

class Pos:
    def __init__(self, l, c, **kw):
        self.l = l
        self.c = c
        self.kw = kw

    def __str__(self):
        return f"{self.l}:{self.c}"

    def __repr__(self):
        return f"Pos({self.l}:{self.c})"

    def copy(self):
        return self.__class__(self.l, self.c, **self.kw)

class Tag(str):
    def __new__(cls, s, l=0, c=0, **kw):
        isend = False
        isplus = False
        if s.startswith("+"):
            isplus = True
            s = s[1:]
        if s.endswith("*"):
            isend = True
            s = s[:-1]
        res = super().__new__(cls, s)
        res.kw = kw
        res.isplus = isplus
        res.isend = isend
        res.pos = Pos(l, c)
        return res

    def __init__(self, s, l=0, c=0):
        self.isplus = getattr(self, 'isplus', False)
        self.isend = getattr(self, 'isend', False)
        self.pos = Pos(l, c)

    def __repr__(self):
        return "Tag("+str(self)+")"

    def __str__(self):
        res = ""
        res += "+" if self.isplus else ""
        res += super().__str__()
        res += "*" if self.isend else ""
        return res

    def basestr(self):
        """ Returns marker with no final *, etc. """
        return super().__str__()

    def setpos(self, pos):
        self.pos = pos

class AttribText(UserString):
    def __init__(self, s, l=0, c=0, **kw):
        super().__init__(s)
        self.pos = Pos(l, c)
        self.kw = kw
    pass

class OptBreak:
    def __init__(self, l=0, c=0, **kw):
        self.pos = Pos(l, c)
        self.kw = kw

    def __repr__(self):
        return "OptBreak(" + str(self) + ")"
    def __str__(self):
        return "//"

class String(UserString):
    def __init__(self, s, l=0, c=0, **kw):
        super().__init__(s)
        self.pos = Pos(l, c)
        self.kw = kw

    def __add__(self, s):
        return String(str(self) + s, l=self.pos.l, c=self.pos.c, **self.kw)

    def be(self, s):
        return String(str(s), l=self.pos.l, c=self.pos.c, **self.kw)

    def addToNode(self, node, position, lstrip=False):
        cp = self.pos.c
        s = str(self)
        if lstrip:
            t = s.lstrip(WS)
            if len(t) < len(s):
                cp += len(s) - len(t)
        else:
            t = s
        currt = getattr(node, position, None)
        if currt is None:
            setattr(node, position, t)
            setattr(node, position+"pos", Pos(self.pos.l, cp, **self.pos.kw))
        else:
            setattr(node, position, currt+t)

class Attribs(UserDict):
    def __init__(self, l=0, c=0, **kw):
        super().__init__()
        self.pos = Pos(l, c)
        self.kw = kw

class Lexer:

    tokenre = regex.compile(r'''    # the next token in text
        ((?: [^\\|/\r\n]            # string component consists of: normal characters
           | \\ (?:[\\|] | \r?\n)           # escaped specials
           | / (?!/)                        # / sequence, not //
          )+                            # one or more of these
        )
        | ( [\\|] | \r?\n | // )    # then specials: tag start or attributes start, newline, //   
    ''', regex.X)
    tagre = regex.compile(r'''
        (?: \+? [a-zA-Z_][a-zA-Z_0-9^-]* )?  # optional + then the usfm tag spec
        \*?                                  # may have a final *
    ''', regex.X)
    attribsre = regex.compile(r'''      # An attribute list
        \s* ([a-zA-Z_][a-zA-Z0-9_-]*)   # whitespace? identifier
        \s* = \s*                       # =
        " ( (?:\\" | [^"])* ) "         # " (escaped " or non quote)* "
    ''', regex.X)
    textrunre = regex.compile(r'''
        (?: [^\\\n] | \\[^a-zA-Z_*+] )*     # nonmagic or escaped single char
    ''', regex.X)
    endattribs = regex.compile(r'\s*\|\s*')
    afterattribs = regex.compile(r'\s*\\')
    usvre = regex.compile(r'(?:\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8}))')

    def __init__(self, txt, parser, expanded=False, strict=False):
        self.txt = txt
        self.expanded = expanded
        self.strict = strict
        self.parser = parser

    def __iter__(self):
        self.nexts = []
        self.cindex = 0
        self.lindex = 0
        self.lpos = 0
        self.lengths = []       # only valid if self.strict
        self.currxpand = None
        return self

    def __next__(self):
        if len(self.nexts):
            return self.nexts.pop(0)
        curri = self.cindex
        res = String("", l=self.lindex, c=curri-self.lpos)
        lastres = None
        while (m := self.tokenre.match(self.txt, pos=curri)):
            curri = m.end()
            if m.group(1):
                res += m.group(1)
                continue
            else:
                lastres = res
            n = m.group(2)

            if n in ("\r\n", "\n"):
                res += n
                self.lengths.append(m.end(2) - self.lpos)
                self.lindex += 1
                self.lpos = m.end(2)
                continue
            elif n == "\\":
                if self.parser.version >= [3, 2]:
                    u = self.usvre.match(self.txt[m.end():])
                    if u:
                        c = chr(int((m.group(1) or m.group(2)), 16))
                        s += c
                        curri += u.end()
                        continue
                t = self.tagre.match(self.txt[m.end():])
                if not t or not t.end():
                    if m.end() < len(self.txt) - 1:
                        s = self.txt[m.end()]
                    if s == "\r" and m.end() < len(self.text) - 2:
                        s += self.txt[m.end()+1]
                    if s in ("\r\n", "\n"):
                        self.lengths.append(m.end() - self.lpos)
                        self.lindex += 1
                        self.lpos += self.lengths[-1]
                    else:
                        res += s
                    curri += len(s)
                    continue
                else:
                    tagname = self.processtag(t.group(0))
                    extras = {"xp": self.currxpand} if self.expanded else {}
                    res = Tag(tagname, l=self.lindex, c=curri-self.lpos, **extras)
                    curri += t.end()
                    break
            elif n == '|':
                t, curri = self.readAttrib(curri)
                if not len(t):
                    res = String("", l=self.lindex, c=curri-self.lpos)
                    continue
                res = t
                break
            elif n == '//':
                res = OptBreak(l=self.lindex, c=curri-self.lpos)
                break
        else:
            lastres = None
        if self.cindex >= curri:
            raise StopIteration
        if lastres:
            self.nexts.append(res)
            res = lastres
        self.cindex = curri
        return res

    def readAttrib(self, curri):
        res = Attribs(l=self.lindex, c=curri-self.lpos)
        resi = curri
        while (m := self.attribsre.match(self.txt[curri:])):
            if "\r" in m.group(2) or "\n" in m.group(2):
                self.error(SyntaxError, f"Newlines not allowed in attributes: {m.group(0)}", self.currpos())
            res[m.group(1)] = self.usvre.sub(lambda x:chr(int(x.group(1) or x.group(2), 16)), m.group(2))    # tests say not to strip()
            if m.end() == 0:
                break
            curri += m.end()
        if not len(res):
            m = self.textrunre.match(self.txt[curri:])
            if m:
                curri += m.end()
                res = AttribText(m.group(0), l=self.lindex, c=curri-self.lpos)  # tests say not to strip()
        frontattrib = False
        if self.parser.version >= [3, 2] and (m := self.endattribs.match(self.txt[curri:])):
            curri += m.end()
            frontattrib = True
        if not frontattrib and not self.afterattribs.match(self.txt[curri:]):
            self.parser.error(SyntaxError, f"Bad end of attributes", self.currpos())
        return res, curri

    def readLine(self):
        m = regex.match(r"(.*?)$", self.txt, pos=self.cindex, flags=regex.M)
        if m:
            self.cindex = m.end() + 1
            self.lindex += 1
            self.lengths.append(self.cindex - self.lpos)
            self.lpos = self.cindex
            self.nexts.append(String(m.group(1)))

    def processtag(self, t):
        i = t.find("^")
        if self.expanded and i >= 0:
            self.currxpand = t[i+1:]
            return t[:i]
        return t

    def appendtag(self, t):
        tag = Tag(t, l=self.lindex, c=self.lpos)
        self.nexts.append(tag)

    def currpos(self):
        return Pos(self.lindex, self.cindex-self.lpos+1)

class Grammar:
    category_markers = {
        "attribute": "cp vp usfm ca va cat",
        "cell": "th1 th2 th3 th4 th5 th6 th7 th8 th9 th10 th11 th12 tc1 tc2 tc3 tc4 tc5 tc6 tc7 tc8 tc9 tc10 tc11 tc12 tcr1 tcr2 tcr3 tcr4 tcr5 tcr6 tcr7 tcr8 tcr9 tcc1 tcc2 tcc3 tcc4 tcc5 tcc6 tcc7 tcc8 tcc9 tcc10 tcc11 tcc12 thc1 thc2 thc3 thc4 thc5 thc6 thc7 thc8 thc9 thc10 thc11 tch12 thr1 thr2 thr3 thr4 thr5 thr6 thr7 thr8 thr9 thr10 thr11 thr12",
        "char": "qac qs add addpn bk dc efm fm fv k nd ndx ord png pn pro qt rq sig sls tl wg wh wa wj jmp no it bdit bd em sc sup w rb",
        "crossreference": "ex x",
        "crossreferencechar": "xt xop xo xta xk xq xot xnt xdc",
        "footnote": "fe f efe ef",
        "footnotechar": "fr ft fk fqa fq fl fw fdc fp",
        "header": "ide h1 h2 h3 h toc1 toc2 toc3 toca1 toca2 toca3",
        "internal": "id c periph v fig esb esbe ref tr rem",
        "introchar": "ior iqt",
        "introduction": "imt1 imt2 imt3 imt4 imte1 imte2 imte imt ib ie iex ili1 ili2 ili imi imq im io1 io2 io3 io4 iot io ipi ipq ipr ip iq1 iq2 iq3 iq is1 is2 is",
        "list": "lh li1 li2 li3 li4 lim1 lim2 lim3 lim4 lim li lf",
        "listchar": "litl lik liv1 liv2 liv3 liv4 liv5 liv",
        "milestone": "ts-s ts-e ts t-s t-e qt1-s qt1-e qt2-s qt2-e qt3-s qt3-e qt4-s qt4-e qt5-s qt5-e qt-s qt-e",
        "otherpara": "sts lit pb p1 p2 qa k1 k2",
        "sectionpara": "restore ms1 ms2 ms3 ms mr mte1 mte2 mte r s1 s2 s3 s4 sr sp sd1 sd2 sd3 sd4 sd s cl cd",
        "title": "mt1 mt2 mt3 mt4 mt",
        "versepara": "cls nb pc pi1 pi2 pi3 pi po pr pmo pmc pmr pm ph1 ph2 ph3 ph p q1 q2 q3 q4 qc qr qm1 qm2 qm3 qm qd q b d mi1 mi2 mi3 mi4 mi m",
        "standalone": "",
    }
    category_tags = {
        "char": ("char", "crossreferencechar", "footnotechar", "introchar", "listchar"),
        "para": ("header", "introduction", "list", "otherpara", "sectionpara", "title", "versepara"),
        "ms": ("milestone", ),
        "note": ("footnote", "crossreference")
    }

    marker_categories = {t:k for k, v in category_markers.items() for t in v.split()}
    marker_tags = {t:k for k, v in category_tags.items() for t in v}

    attribmap = { 'jmp' : 'href', 'k' : 'key', 'qt-s': 'who', 'qt1-s': 'who', 'qt2-s': 'who',
        'qt3-s': 'who', 'qt4-s': 'who', 'qt5-s': 'who', 'rb': 'gloss', 't-s': 'sid', 'ts-s': 'sid',
        'w': 'lemma', 'ref': 'loc', 'xt': 'href' }

    attribtags = { 'cp': 'pubnumber', 'ca': 'altnumber', 'vp': 'pubnumber',
        'va': 'altnumber', 'cat': 'category', 'usfm': 'version'}
    attribvals = {
        "aid?": "imt1 imt2 imt3 imt4 imte1 imte2 imte imt ib ie imi imq im io1 io2 io3 io4 iot io ipc ipi ipq ipr ip iq1 iq2 iq3 iq is1 is2 is iex ilit restore ms1 ms2 ms3 ms mr mte1 mte2 mte r s1 s2 s3 s4 sr sp sd1 sd2 sd3 sd4 sd s cl cd cls nb pc pi1 pi2 pi3 pi po pr pmo pmc pmr pm ph1 ph2 ph3 ph p q1 q2 q3 q4 qc qr qm1 qm2 qm3 qm qd q b d mi1 mi2 mi3 mi4 mi m fe f efe ef ex x fig esb",
        "altnumber?": "c v",
        "caller": "f x fe ef ex efe",
        "category?": "fe f efe ef ex x esb",
        "code": "id",
        "eid?": "c ts-e t-e qt1-e qt2-e qt3-e qt4-e qt5-e qt-e v",
        "gloss?": "rb",
        "href?": "jmp",
        "lemma?": "w",
        "link-href?": "jmp",
        "number?": "c v",
        "pubnumber?": "c v",
        "sid?": "c ts-s t-s qt1-s qt2-s qt3-s qt4-s qt5-s qt-s v",
        "srcloc?": "w",
        "strong?": "w",
        "vid?": "ip iex restore ms1 ms2 ms3 ms mr mte1 mte2 mte r s1 s2 s3 s4 sr sp sd1 sd2 sd3 sd4 sd s cl cd cls nb pc pi1 pi2 pi3 pi po pr pmo pmc pmr pm ph1 ph2 ph3 ph p q1 q2 q3 q4 qc qr qm1 qm2 qm3 qm qd q b d mi1 mi2 mi3 mi4 mi m lit qa lh li1 li2 li3 li4 lim1 lim2 lim3 lim4 lim li lf v",
        "who?": "qt1-s qt2-s qt3-s qt4-s qt5-s qt-s",
    }
    attribsextra = {
        "fig": "alt? copy? file? loc? src? ref size caption",
        "cell": "colspan? align? content?",
        "xt": "href?",
        "ref": "gen? loc",
        "jmp": "title? id?"
    }

    tagre = regex.compile(r"(^t[hc][cr]?\d+)[-_^].*|(.)[_^].*$")

    def __init__(self):
        self.marker_categories = self.marker_categories.copy()
        self.attribmap = self.attribmap.copy()
        self.attributes = {}
        for k, v in self.attribvals.items():
            for u in v.split():
                self.attributes.setdefault(u, []).append(k)
        for k, v in self.attribsextra.items():
            if k in self.category_markers:
                for m in self.category_markers[k].split():
                    self.attributes.setdefault(m, []).extend(v.split())
            else:
                self.attributes.setdefault(k, []).extend(v.split())
        for k, v in self.attribmap.items():
            if k in self.attributes and v in self.attributes[k]:
                continue
            self.attributes.setdefault(k, []).append(v+"?")

    def readmrkrs(self, fname):
        sfm = SFMFile(fname)
        for k, v in sfm.markers.items():
            if 'category' in v:
                b = v['category'].split()[0]
                self.marker_categories[k] = b.lower()
            if 'defattrib' in v:
                self.attribmap[k] = v['defattrib']
            if 'attributes' in v:
                if k in self.attributes:
                    val = set(self.attributes.get(k, [])) + set(v['attributes'].split())
                    self.attributes[k] = sorted(val)

    def parsetag(self, t):
        return self.tagre.sub(r"\1\2", str(t))


def isfirstText(e):
    if e.text is not None and len(e.text):
        return False
    for c in e:
        if not isfirstText(c):
            return False
        if c.tail is not None and len(c.tail):
            return False
    return True

class Node:
    def __init__(self, parser, usxtag, tag, ispara=False, notag=False, pos=None, **kw):
        self.parser = parser
        self.tag = tag
        self.ispara = ispara
        parent = parser.stack[-1] if len(parser.stack) else None
        attribs = kw
        if not notag and tag is not None:
            attribs['style'] = tag
        self.element = parser.factory(usxtag, attribs, parent=getattr(parent, 'element', None), pos=pos)
        if parent:
            parent.addNodeElement(self.element)
        self.attribnodes = []

    def addNodeElement(self, e):
        self.element.append(e)
        e.parent = self.element

    def appendElement(self, child):
        if isinstance(child, OptBreak):
            c = self.parser.factory("optbreak", {}, parent=self.element, pos=child.pos)
            self.element.append(c)
        self.clearAttribNodes()

    def appendText(self, txt):
        if len(self.element):
            if self.element[-1].tail is None or self.element[-1].tail == "":
                txt.addToNode(self.element[-1], 'tail', lstrip=self.ispara and isfirstText(self.element))
            else:
                self.parser.error(SyntaxError,
                            f"Follow on tail {txt} in element {self.element[-1].tag}[{self.element[-1].get('style','')}]",
                            self.element[-1].pos)
                txt.addToNode(self.element[-1], 'tail')
        elif self.element.text is None or self.element.text == "":
            txt.addToNode(self.element, 'text', lstrip=True)
        else:
            self.parser.error(SyntaxError,
                            f"Follow on text {txt} in element {self.element.tag}[{self.element.get('style','')}]",
                            self.element.pos)
            txt.addToNode(self.element, 'text')
        self.clearAttribNodes()

    def addAttributes(self, d):
        self.element.attrib.update({k:v for k, v in d.items()})
        self.clearAttribNodes()

    def addDefaultAttrib(self, t):
        defattrib = self.parser.grammar.attribmap.get(self.tag, None)
        if defattrib is None and self.tag is not None and self.tag.endswith("-e"):
            defattrib = 'eid'
        if defattrib is None:
            defattrib = "_unknown_"
        self.element.set(defattrib, str(t))
        self.clearAttribNodes()

    def addAttribNode(self, node):
        self.attribnodes.append(node)

    def clearAttribNodes(self):
        if not len(self.attribnodes):
            return
        for n in self.attribnodes:
            self.parser.removeParser(n)
        self.attribnodes = []

    def isEmpty(self):
        if not len(self) and self.text is None:
            return True
        return False

    def close(self):
        if getattr(self, 'element', None) is None:
            return
        if len(self.element):
            if self.element[-1].tail is not None and self.ispara:
                self.element[-1].tail = self.element[-1].tail.rstrip(WS)
        elif self.element.text is not None and self.ispara:
            self.element.text = self.element.text.rstrip(WS)
        self.clearAttribNodes()
        
class IdNode(Node):
    def appendText(self, t):
        m = regex.match(r"\s*(\S{3})(?:(.*?))?(?:\n|$)", str(t))
        if m:
            self.element.set('code', m.group(1))
            self.element.text = m.group(2).strip()
            if self.parser:
                self.parser.numbers['id'] = m.group(1)
        self.parser.removeTag('id', absentok=True)

    def addNodeElement(self, e):
        self.parser.stack[0].element.append(e)

class USXNode(Node):
    def appendText(self, t):
        self.element.set('version', str(t).strip(WS))

class AttribNode(Node):
    def __init__(self, parser, parent, tag, pos=None, only=[], **kw):
        self.parser = parser
        self.parent = parent
        self.tag = tag
        self.pos = pos
        self.attribnodes = []
        if len(only) and self.parent.tag not in only:
            self.parser.error(SyntaxError,
                    f"Attrib marker {tag} found after {self.parent.tag} but may only follow {', '.join(only)}",
                    pos)
        self.parent.addAttribNode(self)

    def addNodeElement(self, e):
        self.parent.addNodeElement(e)
        self.parser.removeTag(self.tag)

    def appendText(self, t):
        attrib = self.parent.parser.grammar.attribtags[self.tag]
        self.parent.element.set(attrib, str(t).strip(WS))
        fn = getattr(self.parser, "_"+self.tag+"_", None)
        if fn is not None:
            fn(str(t).strip(WS))

    def dumped(self):
        attrib = self.parent.parser.grammar.attribtags[self.tag]
        self.parent.element.attrib.pop(attrib, None)

class NumberNode(Node):
    def __init__(self, parser, usxtag, tag, ispara=False, pos=None, **kw):
        super().__init__(parser, usxtag, tag, ispara=ispara, pos=pos, **kw)
        self.hasarg = False

    def appendText(self, t):
        if not self.hasarg:
            b = regex.split(r"\s+", str(t).lstrip(WS), 1)
            v = b[0].strip(WS)
            if v[0] not in "0123456789":
                epos = self.element.pos.copy()
                epos.c += 2
                self.parser.error(SyntaxError, f"Bad verse or chapter number: {v}", epos)
            if len(v):
                self.element.set('number', v)
                self.hasarg = True
                if self.parser:
                    self.parser.numbers[self.tag] = v
        else:
            b = ['', str(t)]
        if len(b) > 1 and b[1].strip(WS):
            self.parser.removeTag(self.tag, absentok=True)
            if self.ispara:
                self.parser.addNode(Node(self.parser, 'para', 'p', pos=self.element.pos))
            self.parser.parent = self.parser.stack[-1]  # I don't like this locatoin for this
            self.parser.stack[-1].appendText(String(b[1], t.pos.l, t.pos.c + len(str(t))-len(b[1]), **t.pos.kw))

    def addNodeElement(self, e):
        self.parser.removeTag(self.tag)
        self.parser.stack[-1].addNodeElement(e)

    def close(self):
        if not self.hasarg:
            self.parser.error(SyntaxError, f"Missing number in {self.tag}", self.element.pos)
        super().close()

class NoteNode(Node):
    def __init__(self, parser, usxtag, tag, pos=None, **kw):
        super().__init__(parser, usxtag, tag, pos=pos, **kw)
        self.hascaller = False

    def appendText(self, t):
        if not self.hascaller:
            b = regex.split(r"\s+", str(t).lstrip(WS), 1)
            self.element.set('caller', b[0].strip(WS))
            self.hascaller = True
            if len(b) > 1 and len(b[1]):
                t = t.be(b[1])
            else:
                return
        if self.hascaller:
            super().appendText(t)
            return

class PeriphNode(Node):
    def appendText(self, t):
        t = t.strip(WS)
        if t:
            self.element.set('alt', str(t).strip(WS))

class MsNode(Node):
    def appendText(self, t):
        if not len(t.strip()):
            return
        self.parser.removeTag(self.tag)
        self.parser.parent = self.parser.stack[-1]
        self.parser.parent.appendText(t)

    def appendElement(self, e):
        self.parser.removeTag(self.tag)
        self.parser.parent = self.parser.stack[-1]
        self.parser.parent.appendElement(e)

class UnknownNode(Node):
    pass


paratypes = ('header', 'introduction', 'list', 'otherpara', 'sectionpara', 'versepara', 'title', 'chapter', 'ident')
paratags = ('rem', ' table', 'sidebar')

class USFMParser:

    def __init__(self, txt, factory=None, grammar=None, expanded=False, strict=False, version=[99], index=True, **kw):
        if factory is None:
            def makeel(tag, attrib, **extras):
                attrib.update({" "+k:v for k, v in extras.items()})
                return et.Element(tag, attrib)
            factory = makeel
        if grammar is None:
            grammar = Grammar()
        self.factory = factory
        self.grammar = grammar
        self._setup(expanded=expanded)
        self.lexer = Lexer(txt, self, expanded=expanded, strict=strict)
        self.strict = strict
        self.version = version
        self.doindexing = index
        self.chapters = []
        self.ids = {}
        self.errors = []
        self.numbers = {}

    def _setup(s, expanded=False):
        clsself = s.__class__
        # tag closed types
        for a in (('introchar', 'char'), ('listchar', 'char'), ('_fig', 'figure')):
            def maketype(c, t):
                def dotype(self, tag):
                    if tag.isend:
                        return self.removeTag(str(tag))
                    return self.addNode(Node(self, t, tag.basestr(), pos=tag.pos))
                return dotype
            setattr(clsself, a[0], maketype(*a))
        # implicit closed paras
        for a in paratypes:
            if expanded:
                def dotype(self, tag):
                    self.removeType(paratypes, paratags)
                    return self.addNode(Node(self, 'para', str(tag), pos=tag.pos, ispara=True, xpand=tag.xp))
            else:
                def dotype(self, tag):
                    self.removeType(paratypes, paratags)
                    return self.addNode(Node(self, 'para', str(tag), pos=tag.pos, ispara=True))
            if not hasattr(clsself, a):
                setattr(clsself, a, dotype)

    def parse(self):
        self.result = []
        self.stack = []
        rootnode = Node(self, 'usx', None)
        rootnode.addAttributes({'version': '3.0'})
        self.parent = rootnode
        self.stack.append(rootnode)

        for t in self.lexer:
            if isinstance(t, Tag):
                tag = self.grammar.parsetag(t.basestr())
                if hasattr(self, "_"+tag):
                    tagtype = "_" + tag
                else:
                    tagtype = self.grammar.marker_categories.get(tag, 'internal')
                    if t.basestr() == "":
                        tagtype = "milestone"
                fn = getattr(self, tagtype, self.unknown)
                self.parent = fn(t)
                continue
            if self.parent is None:
                continue
            if isinstance(t, Attribs):
                self.parent.addAttributes(t)
            elif isinstance(t, AttribText):
                self.parent.addDefaultAttrib(t)
            elif isinstance(t, OptBreak):
                self.parent.appendElement(t)
            elif isinstance(t, String):
                self.parent.appendText(t)
        return self.stack[0].element


    def error(self, e, msg, pos):
        self.errors.append((msg, pos, self.cvref()))
        if self.strict:
            raise e(f"{self.cvref()}: {msg} at line {pos.l + 1}, char {pos.c + 1}")

    def removeParser(self, n):
        if n in self.stack:
            self.stack.remove(n)
        if n == self.parent:
            self.parent = self.stack[-1] if len(self.stack) else None

    def addNode(self, node):
        self.stack.append(node)
        return node

    def removeTag(self, tag, absentok=False):
        tag = str(tag).rstrip('*').lstrip('+')      # do what basestr() does
        oldstack = self.stack[:]
        while len(self.stack):
            curr = self.stack.pop()
            curr.close()
            if curr.tag == tag or tag == "" and curr.element.tag == "ms":
                if getattr(curr, 'element', "") == "unk":
                    curr.element.tag = "char"
                break
        else:
            self.stack = oldstack
            if not absentok:
                self.error(SyntaxError, f"Closing {tag} with no opening", self.lexer.currpos())
        return self.stack[-1]

    def removeType(self, t, tags=[]):
        if isinstance(t, str):
            t = [t]
        oldstack = self.stack[:]
        while len(self.stack):
            curr = self.stack.pop()
            if hasattr(curr, 'element'):
                e = curr.element
                if e.tag in ("usx", "periph") or e.tag in tags:
                    self.stack.append(curr)
                    break
                curr.close()
            else:
                curr.close()
                continue
            cat = self.grammar.marker_categories.get(e.get("style", ""), None)
            if e.tag == "unk":
                e.tag = self.grammar.marker_tags.get(t[0], "para")
                if e.tag == 'para' and e.parent is not None:
                    parent = e.parent
                    while parent is not None and parent.tag not in ("usx", "para"):
                        parent = parent.parent
                    if parent.tag != "usx":
                        i, p = parent._getindex()
                        if p is not None:
                            e.parent.remove(e)
                            p.insert(i+1, e)
                            e.parent = p
                            self.removeType(t, tags=tags)
                break
            elif e.tag in tags or cat in t:
                break
        else:
            self.stack = oldstack
        return self.stack[-1] if len(self.stack) else None

    def cvref(self):
        vals = [self.numbers.get(x, '') for x in ("id", "c", "v")]
        return "{} {}:{}".format(*vals)
#### Event methods

    def _c(self, tag):
        self.removeType(paratypes, paratags)
        return self.addNode(NumberNode(self, "chapter", str(tag), ispara=True, pos=tag.pos))

    def _cp(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        elif self.stack[-1].tag == "c":
            parent = AttribNode(self, self.stack[-1], str(tag), pos=tag.pos)
        else:
            parent = Node(self, 'para', str(tag), ispara=True, pos=tag.pos)
        self.stack.append(parent)
        return parent

    def _esb(self, tag):
        self.removeType(paratypes, paratags)
        return self.addNode(Node(self, "sidebar", str(tag), pos=tag.pos))

    def _esbe(self, tag):
        return self.removeTag("esb")

    def _periph(self, tag):
        self.removeTag(str(tag), absentok=True)
        return self.addNode(PeriphNode(self, "periph", str(tag), notag=True, pos=tag.pos))

    def _ref(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        return self.addNode(Node(self, 'ref', tag.basestr(), notag=True, pos=tag.pos))

    def _rem(self, tag):
        if self.version < [3, 2]:
            return self.otherpara(tag)
        if tag.isend:
            return self.removeTag(str(tag))
        self.removeType(paratypes, paratags)
        res = self.addNode(Node(self, 'para', str(tag), ispara=True, pos=tag.pos))
        self.lexer.readLine()
        self.lexer.appendtag("rem*")
        return res

    def _tr(self, tag):
        self.removeTag('tr', absentok=True)
        if not len(self.stack) or self.stack[-1].element.tag != "table":
            self.removeType(paratypes,)
            self.addNode(Node(self, 'table', ' table', notag=True, pos=tag.pos))
        return self.addNode(Node(self, 'row', 'tr', pos=tag.pos))

    def _v(self, tag):
        if len(self.stack) and self.stack[-1].tag == "v":
            self.removeTag('v', absentok=True)
        if len(self.stack) and self.stack[-1].tag == "c":
            self.removeTag('c')
            self.addNode(Node(self, 'para', 'p', pos=tag.pos))
        return self.addNode(NumberNode(self, "verse", str(tag), pos=tag.pos))

    def _vp(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        elif self.stack[-1].tag == "v":
            parent = AttribNode(self, self.stack[-1], str(tag), pos=tag.pos)
        else:
            parent = Node(self, 'char', tag.basestr(), pos=tag.pos)
        self.stack.append(parent)
        return parent

    def _xt(self, tag):
        removed = False
        if self.grammar.marker_categories.get(self.stack[-1].tag, "") == "crossreferencechar":
            res = self.removeType('crossreferencechar')
            removed = True
        if not tag.isend:
            res = self.addNode(Node(self, 'char', tag.basestr(), pos=tag.pos))
        elif not removed:
            res = self.removeTag(tag.basestr())
        return res

    def attribute(self, tag, only=[]):
        if tag.isend:
            return self.removeTag(str(tag))
        try:
            parent = AttribNode(self, self.stack[-1], str(tag), pos=tag.pos, only=only)
        except SyntaxError as e:
            self.errors.append((str(e), tag.pos, self.cvref()))
            parent = Node(self, 'char', tag.basestr(), pos=tag.pos)
        self.stack.append(parent)
        return parent

    def _va(self, tag):
        return self.attribute(tag, only=["v"])

    def _ca(self, tag):
        return self.attribute(tag, only=["c"])

    def cell(self, tag):
        self.removeType('cell', tags=["row"])
        if not tag.isend:
            return self.addNode(Node(self, 'cell', str(tag), pos=tag.pos))
        return self.parent

    def char(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        if len(self.stack) and isinstance(self.stack[-1], AttribNode) \
                and self.stack[-1].tag in ("cp", "vp"):
            a = self.stack[-1]
            self.removeTag(a.tag)
            a.dumped()
            self.addNode(Node(self, 'char', a.tag))
        return self.addNode(Node(self, 'char', tag.basestr()))

    def crossreference(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        return self.addNode(NoteNode(self, 'note', str(tag), pos=tag.pos))

    def crossreferencechar(self, tag):
        res = self.removeType('crossreferencechar', tags=["note"])
        if not tag.isend:
            res = self.addNode(Node(self, 'char', tag.basestr(), pos=tag.pos))
        return res

    def footnote(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        return self.addNode(NoteNode(self, 'note', str(tag), pos=tag.pos))

    def footnotechar(self, tag):
        res = self.removeType('footnotechar', tags=["note"])
        if not tag.isend:
            res = self.addNode(Node(self, 'char', tag.basestr(), pos=tag.pos))
        return res

    def _id(self, tag):
        parent = IdNode(self, "book", str(tag), pos=tag.pos)
        self.lexer.readLine()
        return parent

    def milestone(self, tag):
        if tag.isend:
            return self.removeTag(str(tag))
        return self.addNode(MsNode(self, 'ms', tag.basestr(), pos=tag.pos))

    def standalone(self, tag):
        res = Node(self, 'ms', tag.basestr(), pos=tag.pos)
        return self.stack[-1]

    def unknown(self, tag):
        msg = f"Unknown tag {tag}"
        if len(self.stack):
            msg += f" in {self.stack[-1].tag}"
        self.error(SyntaxError, msg, tag.pos)
        return self.standalone(tag)

    def _usfm_(self, val):
        v = regex.sub(r"(\d+(?:\.\d+)*).*$", r"\1", val)
        try:
            version = [int(x) for x in v.split(".")]
        except ValueError:
            version = None
        self.version = version

def main():
    import sys
    p = USFMParser(sys.argv[1])
    e = p.parse()
    et.indent(e)
    et.dump(e)

if __name__ == '__main__': main()

