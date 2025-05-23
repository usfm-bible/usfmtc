
import re
from functools import reduce
from usfmtc.utils import readsrc

class Versification:

    def __init__(self, fname=None):
        self.toorg = {}         # mappings to org (canonical references)
        self.fromorg = {}       # mappings from org
        self.vnums = {}         # list of verse index to the start of each chapter keyed by book
        self.segments = {}
        self.exclusions = set()
        if fname is not None:
            self.readFile(fname)

    def __getitem__(self, bk):
        return self.vnums.get(bk, None)

    def readFile(self, fname):
        from usfmtc.reference import Ref, books
        srcdat = readsrc(fname)
        for li in srcdat.splitlines():
            l = li.strip()
            l = re.sub(r"#!\s*", "", l)     # remove the magic #!
            l = re.sub(r"\s*#.*$", "", l)   # strip comments
            if not l:
                continue
            if "=" in l:
                ismany = l.startswith("&")
                if ismany:
                    l = l[1:]
                b = l.split("=")
                left = Ref(b[0].strip())
                right = Ref(b[1].strip())
                if ismany:
                    if left.first == left.last:
                        for r in right:
                            self._addMapping(left, r)
                    else:
                        for r in left:
                            self._addMapping(r, right)
                elif left.first == left.last and right.first == right.last:
                    self._addMapping(left, right)
                else:
                    lefts = self._makevlist(left)
                    rights = self._makevlist(right)
                    for r in zip(lefts, rights):
                        self._addMapping(*r)
            elif l.startswith("-"):         # excluded verse
                self.exclusions.add(l[1:].strip())
            elif l.startswith("*"):         # segment list
                b = l[1:].split(",")
                self.segments[b[0].strip()] = [x.strip() for x in b[1:] if "-" not in x]
            else:                           # CV list
                b = l.split()
                if b[0] not in books:
                    continue
                verses = [int(x.split(':')[1]) for x in b[1:]]
                versesums = reduce(lambda a, x: (a[0] + [a[1]+x], a[1]+x), verses, ([0], 0))
                self.vnums[b[0]] = versesums[0]

    def _addMapping(self, left, right):
        self.toorg[str(left)] = right
        self.fromorg[str(right)] = left

    def _makevlist(self, rrange):
        if rrange.first.book != rrange.last.book or rrange.first.chapter != rrange.last.chapter:
            raise ValueError(f"incompatible range: {rrange}")
        res = []
        for i in range(rrange.first.verse, rrange.last.verse + 1):
            r = rrange.first.copy()
            r.verse = i
            res.append(r)
        return res

    def remap(self, ref, other, reverse=False):
        toorg = self.fromorg if reverse else self.toorg
        fromorg = self.toorg if reverse else self.fromorg
        if other is not None:
            otoorg = other.fromorg if reverse else other.toorg
            ofromorg = other.toorg if reverse else other.fromorg
        orgref = toorg.get(str(ref), ref)
        if other is None:
            res = orgref.copy()
        else:
            oorgref = orgref if other is None else otoorg.get(str(ref), ref)
            if ref.book != "ESG" and orgref == oorgref:     # if both ends map to the same org, then they are the same
                res = ref.copy()
            else:
                res = orgref.copy() if other is None else ofromorg.get(str(orgref), orgref).copy()
        res.versification = self if other is None else other
        return res
