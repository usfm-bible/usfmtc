#!/usr/bin/env python3

from typing import Optional, List, Tuple
from dataclasses import dataclass
import re, json, os
from functools import reduce
from collections import UserList

_bookslist = """GEN|50 EXO|40 LEV|27 NUM|36 DEU|34 JOS|24 JDG|21 RUT|4 1SA|31
        2SA|24 1KI|22 2KI|25 1CH|29 2CH|36 EZR|10 NEH|13 EST|10 JOB|42 PSA|150
        PRO|31 ECC|12 SNG|8 ISA|66 JER|52 LAM|5 EZK|48 DAN|12 HOS|14 JOL|3 AMO|9
        OBA|1 JON|4 MIC|7 NAM|3 HAB|3 ZEP|3 HAG|2 ZEC|14 MAL|4 
        MAT|28 MRK|16 LUK|24 JHN|21 ACT|28 ROM|16 1CO|16 2CO|13 GAL|6 EPH|6 PHP|4
        COL|4 1TH|5 2TH|3 1TI|6 2TI|4 TIT|3 PHM|1 HEB|13 JAS|5 1PE|5 2PE|3 1JN|5
        2JN|1 3JN|1 JUD|1 REV|22
        TOB|14 JDT|16 ESG|10 WIS|19 SIR|51 BAR|6 LJE|1 S3Y|1 SUS|1 BEL|1 1MA|16
        2MA|15 3MA|7 4MA|18 1ES|9 2ES|16 MAN|1 PS2|1
        ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 XXA|999 XXB|999 XXC|999
        XXD|999 XXE|999 XXF|999 XXG|999 FRT|0 BAK|999 OTH|999 XXS|0 ZZZ|0 
        ZZZ|0 ZZZ|0 INT|999 CNC|999 GLO|999 TDX|999 NDX|999 DAG|14 ZZZ|0 ZZZ|0
        ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 ZZZ|0 LAO|1"""
        
_hebOrder = ["GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "1SA", "2SA", "1KI",
             "2KI", "ISA", "JER", "EZK", "HOS", "JOL", "AMO", "OBA", "JON", "MIC",
             "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", "PSA", "PRO", "JOB", "SNG",
             "RUT", "LAM", "ECC", "EST", "DAN", "EZR", "NEH", "1CH", "2CH"]
             
_endBkCodes = {'XXG':'100', 'FRT':'A0', 'BAK':'A1', 'OTH':'A2', 'INT':'A7', 'CNC':'A8', 'GLO':'A9',
               'TDX':'B0', 'NDX':'B1', 'DAG':'B2', 'LAO':'C3', 'XXS': '101'} 

_allbooks = ["FRT", "INT", 
            "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI",
            "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG",
            "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC",
            "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", 
            "TOB", "JDT", "ESG", "WIS", "SIR", "BAR", "LJE", "S3Y", "SUS", "BEL", 
            "1MA", "2MA", "3MA", "4MA", "1ES", "2ES", "MAN", "PS2", "DAG", "LAO",
            "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP",
            "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE",
            "1JN", "2JN", "3JN", "JUD", "REV", 
            "XXA", "XXB", "XXC", "XXD", "XXE", "XXF", "XXG", "XXS",
            "GLO", "TDX", "NDX", "CNC", "OTH", "BAK"]

nonScriptureBooks = ["FRT", "INT", "GLO", "TDX", "NDX", "CNC", "OTH", "BAK", "XXA", "XXB", "XXC", "XXD", "XXE", "XXF", "XXG"]

def booknum(bookcode):
    if len(bookcode):
        if bookcode[0] in "ABC":
            return int(bookcode[1:]) + (ord(bookcode[0])-64) * 10 + 100
        else:
            return int(bookcode)
    else:
        return 0

_allbkmap = {k: i for i, k in enumerate(_allbooks)} 

allbooks = [b.split("|")[0] for b in _bookslist.split()] # if b != "ZZZ|0"]
books = dict((b.split("|")[0], i) for i, b in enumerate(_bookslist.split()) if b[-2:] != "|0")
bookcodes = dict((b.split("|")[0], "{:02d}".format(i+1)) for i, b in enumerate(_bookslist.split()[:99]) if b[-2:] != "|0")
bookcodes.update(_endBkCodes)
booknumbers = {k: booknum(v) for k, v in bookcodes.items()}
chaps = dict(b.split("|") for b in _bookslist.split())
oneChbooks = [b.split("|")[0] for b in _bookslist.split() if b[-2:] == "|1"]


@dataclass
class MarkerRef:
    mrkr: str
    index: Optional[int] = None
    word: Optional[int] = None
    char: Optional[str] = None

    def __eq__(self, context:'MarkerRef'):
        if self.mrkr != context.mrkr:
            return False
        elif self.index != context.index:
            return False
        elif self.word != context.word:
            return False
        elif self.char != context.char:
            return False
        return True

    def __str__(self):
        return self.str(force=True)

    def str(self, context: Optional['MarkerRef']=None, force: int=0):
        res = []
        if force > 1 or context is None or context.mrkr != self.mrkr or context.index != self.index:
            res.append("!"+self.mrkr)
            if self.index is not None and self.index > 1:
                res.append("[" + str(self.index) + "]")
        if self.word is not None and (force > 1 or context is None or context.word != self.word):
            if len(res):
                res.append("!")
            res.append(str(self.word))
        if self.char is not None and (force > 1 or context is None or context.char != self.char):
            if len(res):
                res.append("+")
            res.append(str(self.char))
        return "".join([s for s in res if s is not None])

    def copy(self):
        return self.__class__(self.mrkr, self.index, self.word, self.char)

    def getword(self, default=0):
        return self.word or default

    def setword(self, val):
        self.word = val

    def getchar(self, default=0):
        return self.char or default

    def setchar(self, val):
        self.char = val


def intend(s: str) -> Optional[int]:
    if not s:
        return None
    elif s == "end":
        return -1
    return int(s)

def strend(s: int) -> str:
    if s == -1:
        return "end"
    else:
        return str(s)

def parse_wordref(s: str) -> Tuple[int, Optional[str]]:
    b = s.split("+", 1)
    word = int(b[0])
    char = "+" + b[1] if len(b) > 1 else None
    return (word, char)

_reindex = re.compile(r"([0-9a-z_-]+)(?:\[([0-9]+\]))?")
def asmarkers(s: str, t: str) -> List[MarkerRef]:
    res = []
    b = []
    if s is not None and len(s):
        b = s.split("!")
    if t is not None and len(t):
        b += t.split("!")
    i = 0
    while i < len(b):
        if not len(b[i]):
            i += 1
            continue
        if not (m := _reindex.match(b[i])):
            raise SyntaxError("Badly formed marker reference {} in {}".format(b, s))
        mrkr = m.group(1)
        ind = int(m.group(2)) if m.group(2) else None
        if i < len(b) - 1 and len(b[i+1]) and b[i+1][0] in "0123456789":
            word, charref = parse_wordref(b[i+1])
            i += 1
        else:
            word = None
            charref = None
        res.append(MarkerRef(mrkr, index=ind, word=word, char=charref))
        i += 1
    return res if len(res) else None

_bookre = re.compile(r"\A(?:[A-Z][A-Z0-9][A-Z0-9]|[0-9](?:[A-Z][A-Z]|[0-9][A-Z]|[A-Z][0-9]))$")

_regexes = {
    "book": r"""(?P<transid>(?:[a-z0-9_-]*[+])*)
                    (?P<book>\d?{id})
                    (?:\s+{chap})""",
    "booklax": r"""^(?P<transid>(?:[a-z0-9_-]*[+])*)
                    (?P<book>(?!end)\d?{id})
                    (?:\s+{chap})?""",
#    "id": r"(?:[\p{L}\p{Nl}\p{OIDS}-\p{Pat_Syn}-\p{Pat_WS}][\p{L}\p{Nl}\p{OIDS}\p{Mn}\p{Mc}\p{Nd}\p{Pc}\p{OIDC}-\p{Pat_Syn}-\p{Pat_WS}]*)",
    "id": r"(?:[a-z][a-z0-9_-]*[a-z0-9]?)",
    "charref": r"(?:(?:[0-9]|end)[+]?)",
    "wordrefanon": r"",
    "mrkref": r"(?:\!{id}(?:\[[0-9]\])?(?:\!(?:[0-9]|end)(?:[+]{charref})?)?)",
    "wordrefonly": r"(?P<word>[0-9]|end)(?P<char>[+]{charref})?",
    "wordref1": r"""(?:(?: \!(?P<word1>[0-9]|end)(?:[+](?P<char1>{charref}))?
                          |(?P<mrk1>{mrkref}))
                       (?P<mrkn1>{mrkref}*))""",
    "wordref2": r"""(?:(?: \!(?P<word2>[0-9]|end)(?:[+](?P<char2>{charref}))?
                          |(?P<mrk2>{mrkref}))
                       (?P<mrkn2>{mrkref}*))""",
    "verse1": r"(?P<verse1>[0-9]+|end)(?P<subv1>[a-z]?)",
    "verse2": r"(?P<verse2>[0-9]+|end)(?P<subv2>[a-z]?)",
    "chapter": r"(?:(?P<chap>[0-9]+|end))",
    "chap": r"{chapter}(?![a-zA-Z])(?:[:.]{verse1})?{wordref1}?",
    "context": r"""(?:{chap}
                    | {verse2}{wordref2}? | {wordrefonly}(?P<mrkn3>{mrkref}*)
                    | (?P<char3>{charref})(?P<mrkn4>{mrkref}*))(?=[-;,\s]|$)"""
    }

regexes = _regexes
for i in range(3):
    regexes = {k: v.format(**regexes) for k, v in regexes.items()}


class Environment:
    booksep: str = "; "
    chapsep: str = "; "
    versesep: str = ","
    cvsep: str = ":"            # after chap before verse
    bookspace: str = " "        # after the book
    rangemk: str = "-"
    sep: str = "\u200B"
    verseid: str = "v"
    end: str = "end"
    nobook: bool = False
    nochap: bool = False
    __allfields__ = "booksep chapsep versesep cvsep bookspace rangemk sep verseid end nobook nochap".split()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def localbook(self, bk: str, level: Optional[int] = -1) -> str:
        return bk

    def localchapter(self, c: int) -> str:
        return str(c)

    def localverse(self, v: int) -> str:
        if v < 0 or v >= 200:
            return self.end
        else:
            return str(v)

    def parsebook(self, bk: str) -> str:
        if not _bookre.match(bk):
            raise SyntaxError(f"Illegal book name: {bk}")
        return bk

    def copy(self, **kw):
        res = self.__class__()
        for a in self.__allfields__:
            setattr(res, a, kw[a] if a in kw else getattr(self, a))
        return res

class Ref:
    product: Optional[str] = None
    book: Optional[str] = None
    chapter: Optional[int] = None
    verse: Optional[int] = None
    subverse: Optional[str] = None
    word: Optional[int] = None
    char: Optional[int] = None
    mrkrs: Optional[List["MarkerRef"]] = None

    versification: Optional[List[List[int]]] = None
    _rebook = re.compile(regexes["book"], flags=re.X|re.I)
    _rebooklax = re.compile(regexes["booklax"], flags=re.X|re.I)
    _recontext = re.compile(regexes["context"], flags=re.X)
    _parmlist = ('product', 'book', 'chapter', 'verse', 'subverse', 'word', 'char', 'mrkrs')

    def __new__(cls, string: Optional[str] = None,
                    context: Optional['Ref'] = None, start: int = -1, **kw):
        if string is None or start != -1:
            return super().__new__(cls)
        res = RefList(string, context=context, **kw)
        res.simplify()
        if len(res) != 1:
            raise SyntaxError(f"Non contiguous ranges in reference {string}")
        if res[0].__class__ != cls and not isinstance(res[0], RefRange):
            return res[0].copy(cls=cls)
        return res[0]

    @classmethod
    def fromBCV(cls, bcv: int) -> "Ref":
        """ Parses an int BBBCCCVVV into a reference """
        v = bcv % 1000
        b = int(bcv / 1000000)
        c = int((bcv - b * 1000000) / 1000)
        bk = allbooks[b-1]
        return cls(book=bk, chapter=c, verse=v)

    @classmethod
    def loadversification(cls, fname=None):
        from usfmtc.versification import cached_versification
        if fname is None:
            fname = os.path.join(os.path.dirname(__file__), 'org.vrs')
        cls.versification = "Loading"
        cls.versification = cached_versification(fname)
        return cls.versification

    def __init__(self, s: Optional[str]=None,
                    context: Optional['Ref']=None, start:int=0, strict: bool=False, fullmatch: bool=False, **kw):
        if getattr(self, 'chapter', None) is not None:     # We were created in __new__ so skip __init__
            return
        self.strict = strict
        self.env = kw.get('env', None)
        if s is not None:
            if fullmatch and not len(s):
                raise SyntaxError(f"Empty reference string")
            self.parse(s, context=(context.last if context is not None else None), start=start, strict=strict, **kw)
            if self.strend < len(s) and fullmatch:
                raise SyntaxError(f"Extra content after reference {s[0:self.strend]} | {s[self.strend:]}")
        elif context is not None:
            hitlimit = False
            for a in self._parmlist:
                v = kw.get(a, None)
                if v is not None:
                    hitlimit = True
                elif not hitlimit:
                    v = getattr(context.last, a, None)
                setattr(self, a, v)
            if not hasattr(self, 'strend'):
                self.strend = context.strend
        else:
            for a in self._parmlist:
                setattr(self, a, kw.get(a, None))
            if not hasattr(self, 'strend'):
                self.strend = 0
        if 'versification' in kw:
            self.versification = kw['versification']

    def parse(self, s: str, context: Optional['Ref']=None, start: int=0, strict: bool=False, **kw):
        """ Parses a single scripture reference relative to context if given.
            start is an index into the string """
        self.strend = start
        if s is None or not len(s):
            return 
        p = {}
        s = s.strip()
        bookre = self._rebook if strict else self._rebooklax
        if m := bookre.match(s[start:]):
            p['product'] = m.group('transid') or None
            p['book'] = self.parsebook(m.group('book'), strict=strict)
        elif not (m:= self._recontext.match(s[start:])):
            raise SyntaxError("Cannot parse {}".format(s[start:]))
        gs = m.groupdict()
        p['chapter'] = intend(gs.get('chap', None))
        p['verse'] = intend(gs.get('verse1', gs.get('verse2', None)))
        p['subverse'] = gs.get('subv1', gs.get('subv2', None)) or None
        p['word'] = intend(gs.get('word1', gs.get('word2', gs.get('word', None))))
        p['char'] = intend(gs.get('char', gs.get('char1', gs.get('char2', None))))
        mnum = "2" if 'mrk2' in gs else "1"
        p['mrkrs'] = asmarkers(gs.get('mrk'+mnum, None), gs.get('mrkn'+mnum, None))
        if 'book' not in p and context is not None and p['chapter'] is not None and p['verse'] is None and p['word'] is None:
            rep = None
            if context.char is not None:
                rep = 'char'
            elif context.word is not None:
                rep = 'word'
            elif context.verse is not None:
                rep = 'verse'
            if rep is not None:
                p[rep] = p['chapter']
                p['chapter'] = None 
        self.strend = m.end(0) + start
        if p.get('mrkrs', None) == []:
            p['mrkrs'] = None
        if p.get('book', None) in oneChbooks and p['verse'] is None:
            p['verse'] = p['chapter']
            p['chapter'] = 1
        self.__init__(None, context, strict=strict, **p)

    def parsebook(self, bk, strict:bool=True):
        if self.env is not None:
            return self.env.parsebook(bk)
        bk = bk.upper()     # be kind
        if strict and not _bookre.match(bk) or len(bk) > 3:
            raise SyntaxError(f"Illegal book name: {bk}")
        return bk

    def __str__(self):
        return self.str()

    def __repr__(self):
        return "Ref('"+self.str(force=2)+"')"

    def __eq__(self, o):
        if not isinstance(o, Ref):
            return False
        res = all(getattr(self, a) is None or getattr(o, a) is None or getattr(self, a) == getattr(o, a) for a in self._parmlist)
        # res = all(getattr(self, a) == getattr(o, a) for a in self._parmlist)
        return res

    def identical(self, o):
        """ Tests to see if two references are identical """
        if not isinstance(o, Ref):
            return False
        res = all(getattr(self, a) == getattr(o, a) for a in self._parmlist)
        return res

    def __contains__(self, o):
        if isinstance(o, RefRange):
            end = self.end()
            return o.first >= self and o.last <= end
        if self.book != o.book:
            return False
        return all(getattr(self, a) is None or getattr(self, a) == getattr(o, a) for a in self._parmlist)

    def __lt__(self, o):
        """ self entirely precedes o """
        if o is None:
            return False
        elif not isinstance(o, Ref):
            return o > self
        if self.book != o.book:
            return books.get(self.book, 200) < books.get(o.book, 200)
        elif self.chapter != o.chapter:
            return (self.chapter or 0) < (o.chapter or 0)
        elif self.verse != o.verse:
            if self.verse == -1:
                return False
            elif o.verse == -1:
                return True
            return (self.verse or 0) < (o.verse or 0)
        elif self.subverse != o.subverse:
            if self.subverse is None:
                return True
            elif o.subverse is None:
                return False
            else:
                return self.subverse < o.subverse
        elif self.word != o.word:
            if self.word is None:
                return False        # a full verse does not preceded a word in the verse
            return (self.word or 0) < (o.word or 0)
        elif self.char != o.char:
            if self.char is None:
                return False
            return (self.char or 0) < (o.char or 0)
        return False

    def __gt__(self, o):
        """ self comes entirely after o """
        if o is None:
            return True
        return not self <= o

    def __le__(self, o):
        """ self finishes before o finishes """
        return self < o or self in o

    def __ge__(self, o):
        """ self starts after o starts """
        return self > o or self in o

    def __hash__(self):
        return hash(tuple(getattr(self, a, "") for a in self._parmlist))

    def __iter__(self):
        return RefRangeIter(self)

    def str(self, context: Optional['Ref'] = None, force: int = 0, env: Optional['Environment'] = None,
            level: Optional[int] = -1):
        def neqa(c, s, a):
            if getattr(s, a, None) is None:
                return False
            if getattr(c, a, None) is None:
                return True
            return getattr(c, a) != getattr(s, a)
        if env is None:
            env = getattr(self, 'env', None)
        iniforce = force
        if context is None:
            context = Ref()
        else:
            context = context.last
        res = []
        sep = ''
        if (env is None or not env.nobook) and neqa(context, self, 'product'):
            res.append(self.product)
            res.append('.')
            force = max(1, iniforce)
        if (env is None or not env.nobook) and (force > 1 or neqa(context, self, 'book')):
            res.append(env.localbook(getattr(self, 'book', ""), level=level) if env else getattr(self, 'book', ""))
            sep = env.bookspace if env else ' '
            force = max(2, iniforce)
        oneChap = getattr(self, 'book', '') in oneChbooks
        nskipchap = any(getattr(self, a, None) is not None for a in ('chapter', 'verse', 'word'))
        if (env is None or not env.nochap) and not oneChap and nskipchap and (force > 1 or neqa(context, self, 'chapter')):
            if len(res):
                res.append(sep)
            res.append(env.localchapter(getattr(self, 'chapter', 0)) if env else str(getattr(self, 'chapter', 0)))
            sep = env.cvsep if env else ':'
        if getattr(self, 'verse', None) is not None and (force > 1 or neqa(context, self, 'verse')):
            if len(res):
                res.append(sep)
            res.append(env.localverse(getattr(self, 'verse', 0)) if env else strend(getattr(self, 'verse', 0)))
            res.append(getattr(self, 'subverse', '') or "")
            force = max(2, iniforce)
        sep = "!"
        if getattr(self, 'word', None) is not None and (force > 1 or context.word is not None and neqa(context, self, 'word')):
            if len(res):
                res.append(sep)
            res.append(strend(self.word))
            if self.word != 0:
                force = max(2, iniforce)
            else:
                force = iniforce
        else:
            force = iniforce
        sep = "+"
        if getattr(self, 'char', None) is not None and (force > 1 or context.char is not None and neqa(context, self, 'char')):
            if len(res):
                res.append(sep)
            res.append(strend(self.char))
            force = max(2, iniforce)
        else:
            force = iniforce
        sep = "!"
        if getattr(self, 'mrkrs', None) is not None and len(self.mrkrs):
            for i, m in enumerate(self.mrkrs):
                if force < 2 and context is not None and context.mrkrs is not None and i < len(context.mrkrs):
                    if context.mrkrs[i] != m:
                        res.append(m.str(context=context.mrkrs[i], force=force or (len(res) != 0)))
                elif force:
                    res.append(m.str(force=force))
        return "".join([s for s in res if s is not None])

    def bcv(self):
        """ Returns an integer BBBCCCVVV """
        return (books[self.book] * 1000 + self.chapter) * 1000 + self.verse

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def copy(self, cls=None):
        if cls is None:
            cls = self.__class__
        kw = {k: getattr(self, k) for k in self._parmlist}
        if kw.get('mrkrs', None) is not None:
            kw['mrkrs'] = [m.copy() for m in kw['mrkrs']]
        kw['versification'] = self.versification
        return cls(**kw)

    def _setall(self, val):
        res = self.copy()
        for a in ('chapter', 'verse', 'word', 'char'):
            if getattr(self, a, None) is None:
                setattr(res, a, val)
        return res

    def end(self):
        if self.last is not self:
            self.last = self.last.end()
            return self.last
        res = self._setall(-1)
        if res.chapter == -1:
            vrs = self.versification or Ref.loadversification()
            vbk = vrs[bk]
            if vbk is not None:
                res.chapter = len(vrs[bk])
        if res.verse == -1:
            res.verse = self._getmaxvrs(self.book, self.chapter)
        return res

    def start(self):
        if self.first is not self:
            self.first = start(self.first)
            return self.first
        return self._setall(1)

    def expand(self):
        return RefRange(self.start(), self.end())

    def _getmaxvrs(self, bk, chap):
        """ Returns the maximum verse for the book and chapter in this versification """
        if chap is None:
            return 200
        vrs = self.first.versification or Ref.loadversification()
        if isinstance(vrs, str) and vrs == "Loading":
            return 200
        vbk = vrs[bk]
        if vbk is None:
            return 200
        if len(vbk) <= chap:
            maxvrs = -1
        else:
            maxvrs = vbk[chap] - (vbk[chap-1] if chap > 1 else 0)
        return maxvrs

    def isvalid(self):
        """ Returns whether the reference is valid in its versification """
        vrs = self.first.versification or Ref.loadversification()
        if self.book not in books:
            return False
        book = vrs[self.book]
        if book is None or len(book) <= self.chapter:
            return False
        if book[self.chapter] < self.verse:
            return False
        # checking subverse, word and char involves having access to the document
        return True

    def nextverse(self):
        r = self.first.copy()
        maxvrs = self._getmaxvrs(r.book, r.chapter)
        if r.verse is None:
            r.verse = 1
        else:
            r.verse += 1
        if r.verse > maxvrs:
            r.chapter = (r.chapter + 1) if r.chapter is not None else 1
            r.verse = 1
            if r.book not in books:
                r.book = "GEN"
                r.chapter = 1
            elif self.versification is None or r.chapter >= len(self.versification[r.book]):
                newbk = books[r.book] + 1
                while newbk < len(allbooks) and allbooks[newbk] not in books:
                    newbk += 1
                if newbk >= len(allbooks):
                    return None
                r.book = allbooks[newbk]
                r.chapter = 1
        return r

    def allchaps(self):
        return self

    def getword(self, default=0):
        if self.mrkrs is not None and len(self.mrkrs):
            return self.mrkrs[-1].word or default
        else:
            return self.word or default

    def setword(self, val):
        if self.mrkrs is not None and len(self.mrkrs):
            self.mrkrs[-1].word = val
        else:
            self.word = val

    def getchar(self, default=0):
        if self.mrkrs is not None and len(self.mrkrs):
            return self.mrkrs[-1].char or default
        else:
            return self.char or default

    def setchar(self, val):
        if self.mrkrs is not None and len(self.mrkrs):
            self.mrkrs[-1].char = val
        else:
            self.char = val


class RefRange:

    @classmethod
    def fromRef(cls, r):
        return cls(r, r.end())

    def __new__(cls, first: Optional[Ref]=None, last: Optional[Ref]=None, **kw):
        if first is not None and first.identical(last):
            return first
        return super().__new__(cls)

    def __init__(self, first: Optional[Ref]=None, last: Optional[Ref]=None, strict: bool=False, **kw):
        self.strict = strict
        self.first = first.first
        self.last = last.last
        self.strend = first.strend + 1 + last.strend
        if 'sep' in kw:
            self.sep = kw['sep']
        if getattr(self.last, 'book', None) is None:
            self.last.book = self.first.book
        if self.last < self.first:
            raise ValueError(f"{first=} is after {last=}")
        if isinstance(self.first, RefRange):
            raise ValueError(f"Nested RefRange({self.first})")
        if isinstance(self.last, RefRange):
            raise ValueError(f"Nested RefRange({self.last})")

    def __getattr__(self, a):
        if a in Ref._parmlist:
            f = getattr(self.first, a)
            l = getattr(self.last, a)
            if not self.strict or f == l:
                return f
            else:
                raise AttributeError(f"RefRange unequal values for {a}. {f} != {l}")
        raise AttributeError(f"RefRange unknown attribute {a}")

    def str(self, context:Optional[Ref]=None, force:int=0, level:int=-1, env:Optional[Environment]=None):
        res = [self.first.str(context, force=force)]
        res.append(getattr(self, 'sep', "-"))
        res.append(self.last.str(self.first, force=force))
        return "".join(res)

    def __str__(self):
        return self.str()

    def __repr__(self):
        return "RefRange({!r}-{!r})".format(self.first, self.last)

    def __eq__(self, other):
        """ The ranges are identical """
        if not isinstance(other, RefRange):
            return False
        return self.first == other.first and self.last == other.last

    def __lt__(self, o):
        """ We are entirely before the start of the other """
        return self.last < o.first

    def __le__(self, o):
        """ None of us is after the other """
        return not self.last > o.last

    def __gt__(self, o):
        """ We are entirely after the last of the other """
        return self.first > o.last

    def __ge__(self, o):
        """ None of us is before the start of the other """
        return not self.last < o.first

    def __hash__(self):
        return hash((self.first, self.last))

    def __contains__(self, r):
        """ Tests for entire containment of r inside self """
        return r.first >= self.first and r.last <= self.last

    def expand(self):
        self.first = self.first.start()
        self.last = self.last.end()
        return self

    def isvalid(self):
        return self.first.isvalid() and self.last.isvalid()

    def __iter__(self):
        return RefRangeIter(self)

    def __next__(self):
        r = self.first
        while r is not None and r <= self.last:
            yield r
            r = r.nextverse()

    def allchaps(self):
        if self.first.chapter == self.last.chapter:
            yield self
        else:
            yield RefRange(self.first, Ref(book=self.first.book, chapter=self.first.chapter,
                                           verse=self.first._getmaxvrs(self.first.book, self.first.chapter)))
            for i in range(self.first.chapter + 1, self.last.chapter):
                yield Ref(book=self.first.book, chapter=i)
            yield RefRange(Ref(book=self.last.book, chapter=self.last.chapter, verse=1), self.last)

    def copy(self, cls=None):
        if cls is None or not issubclass(cls, RefRange):
            cls = self.__class__
        return cls(self.first, self.last)


class RefRangeIter:

    def __init__(self, base):
        self.r = base.first.copy()
        self.last = base.last

    def __next__(self):
        if self.r is None:
            raise StopIteration
        res = self.r
        if self.r >= self.last:
            self.r = None
        else:
            self.r = self.r.nextverse()
        return res


class RefList(UserList):
    def __init__(self, content: Optional[str | List[Ref | RefRange]] = None,
                context: Optional[Ref]=None, start: int=0, sep: Optional[str]=None, 
                strict: bool=False, **kw):
        if isinstance(content, (list, tuple, RefList)):
            super().__init__(content)
        elif isinstance(content, (Ref, RefRange)):
            super().__init__([content])
        else:
            super().__init__()
            if content is not None and len(content):        # assume it's a str
                self.parse(content, context, start=start, sep=sep, strict=strict, **kw)
        self.strict = strict

    def parse(self, s: str, context: Optional[Ref] = None, start: int = 0, sep: Optional[str] = None, **kw):
        res = []
        if sep is None or all(x in " ,;" for x in sep):
            sep = " ,;"
        start = 0
        lastr = context
        inrange = False
        while start < len(s):
            if s[start] in sep:
                start += 1
                continue
            if (m := re.match("[\u200F\u200E]?-[\u200F\u200E]?", s[start:])):
                rangesep = m.group(0)
                if not len(res) or isinstance(res[-1], RefRange) or res[-1].chapter is None:
                    raise SyntaxError(f"Bad - in {s} ({s[start:]})")
                inrange = True
                start += len(rangesep)
                continue
            r = Ref(s, context=lastr, start=start, fullmatch=False, **kw)
            if inrange:
                res[-1] = RefRange(res[-1], r, sep=rangesep, **kw) if rangesep != "-" else RefRange(res[-1], r, **kw)
                inrange = False
            else:
                res.append(r)
            lastr = r
            start = r.strend
        self.extend(res)

    def __str__(self):
        return self.str()

    def str(self, context: Optional[Ref] = None, force: int = 0, env: Optional['Environment'] = None, **kw):
        res = []
        for r in self:
            if context is not None:
                if context.last.book == r.first.book and context.last.chapter == r.first.chapter:
                    res.append(",")
                else:
                    res.append("; ")
            res.append(r.str(context, force=force, env=env, **kw))
            context = r.last
        return "".join(res)

    def __getattr__(self, a):
        if self.strict:
            raise AttributeError(f"Ref attribute {a} queried on strict list")
        if len(self) and a in Ref._parmlist:
            return getattr(self[0], a)
        raise AttributeError(f"Bad attribute {a} or missing references [{len(self)}]")

    def simplify(self, sort=True):
        res = []
        lastref = Ref()
        temp = []
        count = 0
        if sort:
            self.sort()
        for i,r in enumerate(self):
            t, u = (r.first, r.last)
            if r.first == r.last and r.first.verse is None:
                if isinstance(r, RefRange):
                    r.last = Ref(book=r.first.book, chapter=r.first.chapter)
                else:
                    r = self[i] = RefRange(r.first, Ref(book=r.first.book, chapter=r.first.chapter))
            n = lastref.last.nextverse()
            if lastref.first < t <= lastref.last:
                t = n
            if t > u:
                # print("{} inside {}".format(r, lastref))
                continue
            if t == n and lastref.last.book is not None:
                temp = []
                if isinstance(res[-1], RefRange):
                    res[-1].last = u
                else:
                    res[-1] = RefRange(lastref, u)
            else:
                if len(temp):
                    res.extend(temp)
                    temp = []
                count = 0
                res.append(r)
            lastref = r
        self[:] = res
        return self

    @property
    def first(self):
        return self[0] if len(self) else None

    @property
    def last(self):
        return self[-1] if len(self) else None

    def allrefs(self):
        for r in self:
            yield from r

    def allchaps(self):
        for r in self:
            yield from r.allchaps()

class RefJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Ref, RefRange, RefList)):
            return str(obj)
        elif isinstance(obj, set):
            return sorted(obj)
        return super()(obj)


def main():
    import sys

    if len(sys.argv) > 1:
        s = " ".join(sys.argv[1:])
        res = RefList(s)
        print(res.str(force=1))

if __name__ == "__main__":
    main()
