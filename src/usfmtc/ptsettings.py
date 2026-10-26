""" The settings of a Paratext project. ParatextSettings is a base class that
    applications (e.g. ptxprint) subclass to add their own extras. """

import os, re, logging
import xml.etree.ElementTree as et
from usfmtc.reference import allbooks, bookcodes, _bookslist, BookNamesEnvironment

logger = logging.getLogger(__name__)

ptrefsepvals = {
    'booksep': 'BookSequenceSeparator',
    'chapsep': 'ChapterNumberSeparator',
    'cvsep': 'ChapterVerseSeparator',
    'rangemk': 'RangeIndicator',
    'chaprange': 'ChapterRangeSeparator',
    'bookcsep': 'BookChapterSeparator',
}

# Paratext's versification numbers: 0=unknown 1=original 2=lxx ...
_versifications = ["", "org", "lxx", "vul", "eng", "rsc", "rso"]

_codebooks = {v: k for k, v in bookcodes.items()}      # "41" -> "MAT"
# Paratext book numbers (GEN=1, MAT=40, FRT=100), which index BooksPresent. ZZZ
# entries in the book list are gaps, and its first gap only makes MAT's file code 41.
_ptbooknums = {b: (i+1 if i < 39 else i) for i, b in enumerate(x.split("|")[0]
                    for x in _bookslist.split()) if b != "ZZZ"}
_bookspresentlen = 123


class ParatextSettings:
    """ The settings of a Paratext project, from its Settings.xml """

    settingsfiles = ("Settings.xml", "ptxSettings.xml")

    def __init__(self, prjdir):
        self.dict = {}
        self.ldml = None
        self.prjdir = prjdir
        self.langid = None
        self.bookmap = {}
        self.refenv = None
        self.parse()

    def parse(self):
        for a in self.settingsfiles:
            path = os.path.join(self.prjdir, a)
            if os.path.exists(path):
                try:
                    doc = et.parse(path)
                except et.ParseError as e:
                    logger.error(f"Can't read {path}: {e}")
                    continue
                for c in doc.getroot():
                    self.dict[c.tag] = c.text or ""
                self.calcbookspresent()
                break
        # LanguageIsoCode is code:script:region:variant, e.g. en::: or wsg:Latn::
        self.langid = re.sub('-(?=-|$)', '', self.get('LanguageIsoCode', "unk").replace(":", "-"))
        self.read_ldml()
        self.inferValues()
        path = os.path.join(self.prjdir, "BookNames.xml")
        if os.path.exists(path):
            self.read_bookNames(path)
        else:
            self.default_bookNames()
        self.set_versification()
        return self

    def set_versification(self):
        """ Sets vrsname to the name of the project's standard versification (e.g. eng),
            and versification to the file in the project to read, if there is one """
        self.versification = None
        self.vrsname = None
        self._vrs = None
        v = self.get('Versification', "")
        if v.isdigit() and int(v) < len(_versifications):
            self.vrsname = _versifications[int(v)] or None
            if self.vrsname is not None and os.path.exists(os.path.join(self.prjdir, self.vrsname+".vrs")):
                self.versification = self.vrsname + ".vrs"
        if self.versification is None and os.path.exists(os.path.join(self.prjdir, "custom.vrs")):
            self.versification = "custom.vrs"
        return self

    def getVersification(self):
        """ The project's versification: its standard versification (from the project
            or bundled with usfmtc) with any custom.vrs read on top. None if there is none. """
        if self._vrs is not None:
            return self._vrs
        from usfmtc.versification import Versification
        files = []
        if self.vrsname is not None:
            for d in (self.prjdir, os.path.dirname(__file__)):
                path = os.path.join(d, self.vrsname+".vrs")
                if os.path.exists(path):
                    files.append(path)
                    break
            else:
                logger.warning(f"No {self.vrsname} versification for {self.prjdir}")
        path = os.path.join(self.prjdir, "custom.vrs")
        if os.path.exists(path):
            files.append(path)
        if not len(files):
            return None
        if len(files) == 1 and files[0] != path:    # only the standard one, which can be shared
            from usfmtc.versification import cached_versification
            bundled = os.path.dirname(files[0]) == os.path.dirname(__file__)
            # a bundled one by name, as others ask for it, so they get the same object
            self._vrs = cached_versification(self.vrsname if bundled else files[0])
            return self._vrs
        self._vrs = Versification()
        for f in files:
            self._vrs.readFile(f)
        return self._vrs

    def read_ldml(self):
        """ Reads the project's <langid>.ldml. Subclasses extend this to pull more from it """
        self.ldml = None
        fname = os.path.join(self.prjdir, self.langid+".ldml")
        if os.path.exists(fname):
            try:
                self.ldml = et.parse(fname)
            except et.ParseError as e:
                logger.error(f"Can't read {fname}: {e}")

    def find_ldml(self, path):
        if self.ldml is None:
            return None
        return self.ldml.find(path)

    def read_bookNames(self, fpath):
        self.booknames = BookNamesEnvironment()
        self.hasLocalBookNames = False
        try:
            self.booknames.readBookNames(fpath)
        except et.ParseError as e:
            logger.error(f"Can't read {fpath}: {e}")
            return
        self.hasLocalBookNames = True

    def default_bookNames(self):
        self.booknames = BookNamesEnvironment()
        self.hasLocalBookNames = False

    def getRefEnvironment(self, booknames=None):
        """ The book names (these, else the project's) with the project's reference separators """
        if booknames is None and self.refenv:
            return self.refenv
        res = (booknames or self.booknames).copy()
        for k, v in ptrefsepvals.items():
            if v in self.dict:
                setattr(res, k, re.sub(r"^(.*?)(\|.*)?$", r"\1", self.dict[v]))
        if self.dict.get('NoSpaceBetweenBookAndChapter', "False") == "True":
            res.bookspace = ''
        if booknames is None:
            self.refenv = res
        return res

    def __getitem__(self, key):
        return self.dict[key]

    def get(self, key, default=None):
        res = self.dict.get(key, default)
        if res is None:
            return default
        return res

    def inferValues(self, forced=False):
        """ Works out the book file naming from the files, if the settings don't give it """
        if forced or 'FileNameBookNameForm' not in self.dict and os.path.exists(self.prjdir):
            sfmfiles = [x for x in os.listdir(self.prjdir) if x.lower().endswith("sfm")]
            for f in sfmfiles:
                m = re.search(r"(\d{2})", f)
                if not m or m.group(1) not in _codebooks:
                    ei = f.rfind(".")
                    if ei > 0:
                        for i in range(len(f)-ei-2):
                            if f[i:i+3].upper() in allbooks:
                                bk = f[i:i+3].upper()
                                numi = i
                                break
                        else:
                            continue
                    else:
                        continue
                else:
                    bk = _codebooks[m.group(1)]
                    numi = m.start(1)
                bki = f.lower().find(bk.lower())
                if bki < 0:
                    continue
                s = min(bki, numi)
                e = max(bki+3, numi+2)
                (pre, main, post) = f[:s], f[s:e], f[e:]
                self.dict['FileNamePrePart'] = pre or ""
                self.dict['FileNamePostPart'] = post or ""
                main = main[:numi-s] + "41" + main[numi-s+2:]
                main = main[:bki-s] + "MAT" + main[bki-s+3:]
                self.dict['FileNameBookNameForm'] = main
                break
        if 'BooksPresent' not in self.dict:
            self.calcbookspresent(inferred=forced)
        self.set_versification()

    def _bookfmt(self):
        fbkfm = self.get('FileNameBookNameForm', "")
        return self.get('FileNamePrePart', "") + \
               fbkfm.replace("MAT", "{bkid}").replace("41", "{bkcode}") + \
               self.get('FileNamePostPart', "")

    def calcbookspresent(self, inferred=False, forced=False):
        self.bookmap = {}
        booksfound = set()
        bookspresent = [0] * _bookspresentlen

        def addbook(bk, fname):
            self.bookmap[bk] = fname
            booksfound.add(fname)
            i = _ptbooknums.get(bk, 0) - 1
            if 0 <= i < len(bookspresent):
                bookspresent[i] = 1

        if not inferred and 'FileNameBookNameForm' in self.dict:
            bknamefmt = self._bookfmt()
            for k in allbooks:
                fname = bknamefmt.format(bkid=k, bkcode=bookcodes.get(k, "00"))
                if os.path.exists(os.path.join(self.prjdir, fname)):
                    addbook(k, fname)
            if not len(booksfound) and not forced:     # buggy Settings.xml that doesn't fit the directory tree
                self.inferValues(forced=True)
                self.calcbookspresent(forced=True)
                return
        elif os.path.exists(self.prjdir):
            for f in os.listdir(self.prjdir):
                if not f.lower().endswith("sfm") or f in booksfound or f.lower().startswith("regexbackup"):
                    continue
                with open(os.path.join(self.prjdir, f), encoding="utf-8", errors="ignore") as inf:
                    m = re.match(r"^﻿?\\id\s+(\S{3})\s*", inf.readline())
                if m:
                    addbook(m.group(1).upper(), f)
        self.dict['BooksPresent'] = "".join(str(x) for x in bookspresent)

    def getBookFilename(self, bk):
        if bk in self.bookmap:
            return self.bookmap[bk]
        return self._bookfmt().format(bkid=bk, bkcode=bookcodes.get(bk, "00"))

    def getBookPath(self, bk):
        """ The path to the book's file, or None if it isn't there """
        path = os.path.join(self.prjdir, self.getBookFilename(bk))
        return path if os.path.exists(path) else None

    def getABook(self, bk=None):
        """ The first book present after bk """
        try:
            start = allbooks.index(bk) + 1
        except ValueError:
            start = 0
        for b in allbooks[start:]:
            if self.getBookPath(b) is not None:
                return b
