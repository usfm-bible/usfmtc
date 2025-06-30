
import re, os
from functools import reduce
from usfmtc.utils import readsrc, get_trace
from usfmtc.reference import RefRange
import logging

logger = logging.getLogger(__name__)

versifications = {}

def cached_versification(fname):
    if fname is None:
        return None
    if fname not in versifications:
        if os.path.exists(fname):
             versifications[fname] = Versification(fname)
        fpath = os.path.join(os.path.dirname(__file__), fname + ".vrs")
        if os.path.exists(fpath):
            versifications[fname] = Versification(fpath)
    return versifications.get(fname, None)

class Versification:

    def __init__(self, fname=None):
        self.toorg = {}         # mappings to org (canonical references)
        self.fromorg = {}       # mappings from org
        self.vnums = {}         # list of verse index to the start of each chapter keyed by book
        self.segments = {}
        self.exclusions = set()
        self.name = None
        if fname is not None:
            self.readFile(fname)

    def __getitem__(self, bk):
        return self.vnums.get(bk, None)

    def readFile(self, fname):
        from usfmtc.reference import Ref, books
        logger.debug(f"versification readFile({fname})")
        srcdat = readsrc(fname)
        for li in srcdat.splitlines():
            l = li.strip()
            if self.name is None and (m := re.match(r'^#\s+versification\s*"(.*?)"', l, flags=re.I)):
                self.name = m.group(1)
                continue
            l = re.sub(r"#!\s*", "", l)     # remove the magic #!
            l = re.sub(r"\s*#.*$", "", l)   # strip comments
            if not l:
                continue
            if "=" in l:
                ismany = l.startswith("&")
                if ismany:
                    l = l[1:]
                b = l.split("=")
                left = Ref(b[0].strip(), versification=self)
                right = Ref(b[1].strip(), versification=self)
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

    def _addOneMapping(self, mapping, left, right):
        if str(left) in mapping:
            r = mapping[str(left)]
            if isinstance(r, RefRange):
                if right.last < r.first:
                    r.first = right.first
                elif right.first > r.last:
                    r.last = right.last
            else:
                if right.last < r:
                    r = RefRange(right.first, r)
                else:
                    r = RefRange(r, right.last)
                mapping[str(left)] = r
        else:
            mapping[str(left)] = right

    def _addMapping(self, left, right):
        self._addOneMapping(self.toorg, left, right)
        self._addOneMapping(self.fromorg, right, left)

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
        ''' maps a reference from this mapping to org, or reverse if set '''
        from usfmtc.reference import RefRange
        if isinstance(ref, RefRange):
            first = self.remap(ref.first, other, reverse=reverse)
            last = self.remap(ref.last, other, reverse=reverse)
            return RefRange(first, last)
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

    def issame_map(self, other):
        if self.name is not None and other.name == self.name:
            return True
        if len(self.toorg) != len(other.toorg) or len(self.fromorg) != len(other.fromorg):
            return False
        if any(v != other.toorg.get(k, None) for k, v in self.toorg.items()):
            return False
        if any(v != other.fromorg.get(k, None) for k, v in self.fromorg.items()):
            return False
        return True


def main():
    import argparse, os, sys
    from usfmtc import readFile

    parser = argparse.ArgumentParser()
    parser.add_argument("infile", nargs="+", help="Input files or directory")
    parser.add_argument("-o", "--outfile", default=".", help="Output file or directory")
    parser.add_argument("-f", "--from", help="from versification file")
    parser.add_argument("-t", "--to", help="to versification file")
    parser.add_argument("-k", "--keep", action="store_true", help="Add vp for change verse numbers")
    parser.add_argument("-C", "--withcnums", action="store_true", help="with --keep include chapter numbers if different")
    args = parser.parse_args()

    argfr = getattr(args, 'from', None)
    fromv = Versification(argfr) if argfr is not None else None
    tov = Versification(args.to) if args.to is not None else None

    infiles = []
    for inf in args.infile:
        if os.path.isdir(inf):
            for f in os.listdir(inf):
                if f.lower().endswith("sfm"):
                    infiles.append(os.path.join(inf, f))
        elif os.path.exists(inf):
            infiles.append(inf)

    jobs = []
    if len(infiles) > 1 and not os.path.isdir(args.outfile):
        print("Can't map multiples files onto one")
        sys.exit(1)
    elif not os.path.isdir(args.outfile):
        jobs = [(infiles[0], args.outfile)]
    else:
        for inf in infiles:
            jobs.append((inf, os.path.join(args.outfile, os.path.basename(inf))))

    for j in jobs:
        usx = readFile(j[0])
        usx.reversify(fromv, tov, keep=args.keep, chnums=args.withcnums)
        usx.saveAs(j[1])

if __name__ == "__main__":
    main()
