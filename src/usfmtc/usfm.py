""" Collections of USFM books """

import os, re
from usfmtc.reference import allbooks, BookNamesEnvironment


class UsfmCollection:
    """ The books of a project, read when first asked for and cached """

    def __init__(self, bkmapper, basedir, grammar=None):
        self.bkmapper = bkmapper        # book id -> file path, or None
        self.basedir = basedir
        self.grammar = grammar
        self.books = {}
        self.booknames = None

    def readbook(self, bk, bkfile):
        """ Reads a book's file. Subclasses override this to transform or wrap the result """
        from usfmtc import readFile
        return readFile(bkfile, informat="usfm", grammar=self.grammar)

    def get(self, bk):
        if bk not in self.books:
            bkfile = self.bkmapper(bk)
            if bkfile is None or not os.path.exists(bkfile):
                return None
            self.books[bk] = self.readbook(bk, bkfile)
        return self.books[bk]

    def getusx(self, bk):
        """ The book as a USX document, or None. Subclasses whose get() returns
            something else override this. """
        return self.get(bk)

    def clear(self, bk):
        self.books.pop(bk, None)

    def makeBookNames(self):
        """ Book names from BookNames.xml, else from each book's \\toc1-3 """
        if self.booknames is not None:
            return self.booknames
        self.booknames = BookNamesEnvironment()
        bknamesp = os.path.join(self.basedir, "BookNames.xml")
        if os.path.exists(bknamesp):
            self.booknames.readBookNames(bknamesp)
            return self.booknames
        tocre = re.compile(r"^\\toc([123])\s+(.*?)\s*$")
        for bk in allbooks:
            bkfile = self.bkmapper(bk)
            if bkfile is None or not os.path.exists(bkfile):
                continue
            tocs = [""] * 3         # long, short, abbr
            with open(bkfile, encoding="utf-8") as inf:
                for l in inf:
                    if '\\c ' in l:
                        break
                    m = tocre.match(l)
                    if m:
                        tocs[int(m.group(1))-1] = m.group(2)
            if not any(tocs):
                continue
            for i in (1, 0):        # a missing name falls back to the next shorter
                tocs[i] = tocs[i] or tocs[i+1]
            for i in (1, 2):        # or else to the next longer
                tocs[i] = tocs[i] or tocs[i-1]
            self.booknames.addBookName(bk, tocs[2], tocs[1], tocs[0])
        return self.booknames
