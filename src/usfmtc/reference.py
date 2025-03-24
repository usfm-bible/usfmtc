#!/usr/bin/env python3

from typing import Optional, List, Tuple
from dataclasses import dataclass
import re, json, os
from functools import reduce

_bookslist = """GEN|50 EXO|40 LEV|27 NUM|36 DEU|34 JOS|24 JDG|21 RUT|4 1SA|31
        2SA|24 1KI|22 2KI|25 1CH|29 2CH|36 EZR|10 NEH|13 EST|10 JOB|42 PSA|150
        PRO|31 ECC|12 SNG|8 ISA|66 JER|52 LAM|5 EZK|48 DAN|12 HOS|14 JOL|3 AMO|9
        OBA|1 JON|4 MIC|7 NAM|3 HAB|3 ZEP|3 HAG|2 ZEC|14 MAL|4 ZZZ|0
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

    def __str__(self):
        return self.str(force=True)

    def str(self, context: Optional['MarkerRef']=None, force: bool=False):
        res = []
        if force or context is None or context.mrkr != self.mrkr or context.index != self.index:
            res.append("!"+self.mrkr)
            if self.index is not None:
                res.append("[" + str(self.index) + "]")
        if self.word is not None and (force or context is None or context.word != self.word):
            if len(res):
                res.append("!")
            res.append(str(self.word))
        if self.char is not None and (force or context is None or context.char != self.char):
            if len(res):
                res.append("+")
            res.append(str(self.char))
        return "".join(res)

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
    if s is None or not len(s):
        return res
    b = s.split("!")
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

def readvrs(fname):
    ''' res[book number] [0] versenum of start of book from start of Bible
                         [1..n] number of verses from start of book to end of chapter'''
    res = [[] for i in range(len(allbooks))]
    with open(fname, encoding="utf-8") as inf:
        for li in inf.readlines():
            l = li.strip()
            if l.startswith("#"):
                continue
            b = l.split()
            if not len(b) or (len(b) == 5 and b[2] == "="):
                continue
            if b[0] not in books:
                continue
            verses = [int(x.split(':')[1]) for x in b[1:]]
            versesums = reduce(lambda a, x: (a[0] + [a[1]+x], a[1]+x), verses, ([0], 0))
            res[books[b[0]]] = versesums[0]
    curr = 0
    for b in res:
        if len(b):
            b[0] = curr
            curr += b[-1] + len(b) - 1
        else:
            b.append(curr)
    return res


_regexes = {
    "book": r"""(?P<transid>(?:[a-z0-9_-]*[+])*)
                    (?P<book>(?:[A-Z][A-Z0-9][A-Z0-9]|[0-9](?:[A-Z][A-Z]|[0-9][A-Z]|[A-Z][0-9])))
                    \s*{chap}""",
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
    "chap": r"{chapter}(?:[:.]{verse1})?{wordref1}?",
    "context": r"""(?:{chap}
                    | {verse2}{wordref2}? | {wordrefonly}(?P<mrkn3>{mrkref}*)
                    | (?P<char3>{charref})(?P<mrkn4>{mrkref}*))(?=[-;,\s]|$)"""
    }

regexes = _regexes
for i in range(3):
    regexes = {k: v.format(**regexes) for k, v in regexes.items()}


class Ref:
    product: Optional[str]
    book: Optional[str]
    chapter: Optional[int]
    verse: Optional[int]
    subverse: Optional[str]
    word: Optional[int]
    char: Optional[int]
    mrkrs: Optional[List["MarkerRef"]]

    versification: Optional[List[List[int]]] = None
    _rebook = re.compile(regexes["book"], flags=re.X)
    _recontext = re.compile(regexes["context"], flags=re.X)
    _parmlist = ('product', 'book', 'chapter', 'verse', 'subverse', 'word', 'char', 'mrkrs')

    def __new__(cls, string: Optional[str] = None,
                    context: Optional['Ref'] = None, start: int = 0, **kw):
        if string is None or "-" not in string:
            return super().__new__(cls)
        bits = string.split("-", 1)
        start = Ref(bits[0], context)
        end = Ref(bits[1], start)
        return RefRange(start, end)

    @classmethod
    def loadversification(cls, fname=None):
        if fname is None:
            fname = os.path.join(os.path.dirname(__file__), 'eng.vrs')
        cls.versification = readvrs(fname)
        return cls.versification

    def __init__(self, string: Optional[str] = None,
                    context: Optional['Ref'] = None, start: int = 0, **kw):
        if string is not None:
            s = string.strip()
            self.parse(s, context=(context.last if context is not None else None), start=start)
            if self.strend < len(s):
                raise SyntaxError(f"Extra content after reference {s[0:self.strend]} | {s[self.strend:]}")
            return

        if context is not None:
            hitlimit = False
            for a in self._parmlist:
                v = kw.get(a, None)
                if v is not None:
                    hitlimit = True
                elif not hitlimit:
                    v = getattr(context.last, a, None)
                setattr(self, a, v)
        else:
            for a in self._parmlist:
                setattr(self, a, kw.get(a, None))

    def parse(self, s: str, context: Optional['Ref'] = None, start: int = 0):
        if "-" in s:
            return 
        p = {}
        s = s.strip()
        if m := self._rebook.match(s, pos=start):
            p['product'] = m.group('transid') or None
            p['book'] = m.group('book')
        elif not (m:= self._recontext.match(s, pos=start)):
            raise SyntaxError("Cannot parse {}".format(s))
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
        self.strend = m.end(0)
        if p.get('mrkrs', None) == []:
            p['mrkrs'] = None
        if p.get('book', None) in oneChbooks and p['verse'] is None:
            p['verse'] = p['chapter']
            p['chapter'] = 1
        self.__init__(None, context, **p)

    def __str__(self):
        return self.str()

    def __repr__(self):
        return "Ref("+self.str()+")"

    def __eq__(self, o):
        if not isinstance(o, Ref):
            return False
        res = all(getattr(self, a) is None or getattr(o, a) is None or getattr(self, a) == getattr(o, a) for a in self._parmlist)
        return res

    def __contains__(self, o):
        if isinstance(o, RefRange):
            selfr = RefRange.fromRef(self)
            return o in selfr
        if self.book != o.book:
            return False
        return all(getattr(self, a) is None or getattr(self, a) == getattr(o, a) for a in self._parmlist)

    def __lt__(self, o):
        if o is None:
            return False
        elif not isinstance(o, Ref):
            return not o < self or o == self
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
            return (self.word or 0) < (o.word or 0)
        elif self.char != o.char:
            return (self.char or 0) < (o.char or 0)
        return False

    def __gt__(self, o):
        if o is None:
            return True
        return o < self

    def __le__(self, o):
        return not self > o

    def __ge__(self, o):
        return not self < o

    def __hash__(self):
        return hash((getattr(self, a) for a in self._parmlist))

    def str(self, context: Optional['Ref'] = None, force: bool = False):
        if context is None:
            context = Ref()
        else:
            context = context.last
        res = []
        sep = ''
        if context.product != self.product:
            res.append(self.product)
            res.append('.')
            force = True
        if force or context.book != self.book:
            res.append(self.book)
            res.append(' ')
            force = True
        if self.book not in oneChbooks and (force or context.chapter != self.chapter):
            res.append(str(self.chapter))
            sep = ':'
        if self.verse is not None and (force or context.verse != self.verse):
            if len(res):
                res.append(sep)
            res.append(strend(self.verse))
            res.append(self.subverse or "")
        sep = "!"
        if self.word is not None and (force or context.word != self.word):
            if len(res):
                res.append(sep)
            res.append(strend(self.word))
        sep = "+"
        if self.char is not None and (force or context.char != self.char):
            if len(res):
                res.append(sep)
            res.append(strend(self.char))
        sep = "!"
        if self.mrkrs is not None and len(self.mrkrs):
            forcemkr = False
            for i, m in enumerate(self.mrkrs):
                if not forcemkr and context is not None and context.mrkrs is not None and i < len(context.mrkrs):
                    if context.mrkrs[i] != m:
                        res.append(m.str(context=contex.mrkrs[i], force=force or len(res)))
                        forcemkr = True
                elif force or forcemkr:
                    res.append(m.str(force=True))
        return "".join(res)

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def copy(self):
        kw = {k: getattr(self, k) for k in self._parmlist}
        return self.__class__(**kw)

    def _setall(self, val):
        res = self.copy()
        for a in ('chapter', 'verse', 'word', 'char'):
            if getattr(self, a, None) is None:
                setattr(res, a, val)
        return res

    def end(self):
        if self.last != self:
            self.last = end(self.last)
            return self.last
        res = self._setall(-1)
        if res.chapter == -1:
            vrs = self.versification or Ref.loadversification()
            book = books.get(self.book, None)
            if book is not None:
                res.chapter = len(vrs[book])
        if res.verse == -1:
            res.verse = self._getmaxvrs(self.book, self.chapter)
        return res

    def start(self):
        if self.first != self:
            self.first = start(self.first)
            return self.first
        return self._setall(1)

    def expand(self):
        return RefRange(self.start(), self.end())

    def _getmaxvrs(self, bk, chap):
        vrs = self.first.versification or Ref.loadversification()
        book = books.get(bk, None)
        if book is None or len(vrs[book]) <= chap:
            maxvrs = -1
        else:
            maxvrs = vrs[book][chap] - (vrs[book][chap-1] if chap > 1 else 0)
        return maxvrs

    def isvalid(self):
        vrs = self.first.versification or Ref.loadversification()
        if self.book not in books:
            return False
        book = vrs[books.get(self.book)]
        if len(book) < self.chapter:
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
            elif r.chapter >= len(self.versification[books[r.book]]):
                newbk = books[r.book] + 1
                while newbk < len(allbooks) and allbooks[newbk] not in books:
                    newbk += 1
                if newbk >= len(allbooks):
                    return None
                r.book = allbooks[newbk]
                r.chapter = 1
        return r


class RefRange:

    @classmethod
    def fromRef(cls, r):
        return cls(r, r.end())

    def __init__(self, first: Optional[Ref]=None, last: Optional[Ref]=None):
        self.first = first
        self.last = last
        if self.last < self.first:
            raise ValueError(f"{first=} is after {last=}")

    def str(self, context: Optional[Ref] = None, force: bool = False):
        res = [self.first.str(context, force=force)]
        res.append("-")
        res.append(self.last.str(self.first, force=force))
        return "".join(res)

    def __str__(self):
        return self.str()

    def __repr__(self):
        return "RefRange({!r}-{!r})".format(self.first, self.last)

    def __eq__(self, other):
        if not isinstance(other, RefRange):
            return False
        return self.first == other.first and self.last == other.last

    def __lt__(self, o):
        return self.last <= o.first

    def __le__(self, o):
        return self.last <= o.last

    def __gt__(self, o):
        return self.first >= o.last

    def __ge__(self, o):
        return self.first >= o.first

    def __hash__(self):
        return hash((self.first, self.last))

    def __contains__(self, r):
        return self.first <= r.last and r.first <= self.last

    @property
    def strend(self):
        return self.last.strend

    def expand(self):
        self.first = self.first.start()
        self.last = self.last.end()
        return self

    def isvalid(self):
        return self.first.isvalid() and self.last.isvalid()

    def allverses(self):
        r = self.first
        while r is not None and r <= self.last:
            yield r
            r = r.nextverse()


class RefList(List):
    def __init__(self, content: str | List[Ref | RefRange], context: Optional[Ref] = None, start: int = 0):
        if isinstance(content, list):
            super().__init__(content)
        else:
            self.parse(content, context, start=start)

    def parse(self, s: str, context: Optional[Ref] = None, start: int = 0):
        bits = re.split(r"\s*[,;]\s*", s[start:])
        res = []
        for b in bits:
            r = Ref(b, context=context)
            res.append(r)
            context = r
        self.__init__(res)

    def __str__(self):
        return self.str()

    def str(self, context: Optional[Ref] = None, force: bool = False):
        res = []
        for r in self:
            if context is not None:
                if context.last.book == r.first.book and context.last.chapter == r.first.chapter:
                    res.append(",")
                else:
                    res.append("; ")
            res.append(r.str(context, force=force))
            context = r.last
        return "".join(res)

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
                    r.last = Ref(book=r.first.book, chapter=r.first.chapter, verse=-1)
                else:
                    r = self[i] = RefRange(r.first, Ref(book=r.first.book, chapter=r.first.chapter, verse=-1))
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



class RefJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Reference, RefRange, RefList)):
            return str(obj)
        elif isinstance(obj, set):
            return sorted(obj)
        return super()(obj)


def main():
    import sys

    if len(sys.argv) > 1:
        s = " ".join(sys.argv[1:])
        res = RefList(s)
        print(res.str(force=True))

if __name__ == "__main__":
    main()
