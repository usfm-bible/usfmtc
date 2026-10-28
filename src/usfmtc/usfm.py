""" Reading and writing USFM, USX and USJ documents """

import os, re, json, io
from usfmtc.utils import readsrc, getSrcName
from usfmtc.validating.usfmparser import parseusfm, UsfmParserBackend
from usfmtc.extension import Extensions
from usfmtc.xmlutils import ParentElement, prettyxml, writexml
from usfmtc.validating.usxparser import USXConverter
from usfmtc.validating.usfmgrammar import UsfmGrammarParser
from usfmtc.usxmodel import addesids, cleanup, canonicalise, reversify, \
                            iterusx, iterusxref, \
                            regularise, clear_empties, addorncv
from usfmtc.usxcursor import USXCursor
from usfmtc.usjproc import usxtousj, usjtousx
from usfmtc.usfmparser import USFMParser, Grammar
from usfmtc.usfmgenerate import usx2usfm
from usfmtc.reference import allbooks, BookNamesEnvironment
import xml.etree.ElementTree as et

def _grammarDoc(gsrc, extensions=[], factory=et):
    data = readsrc(gsrc)
    if isinstance(data, (str, bytes)):
        rdoc = factory.ElementTree(factory.fromstring(data))
    else:
        rdoc = data
    for ef in extensions:
        e = Extensions(ef)
        dirty = e.applyto(rdoc, factory=factory)
    return rdoc

def _usfmGrammar(rdoc, backend=None, start=None):
    if backend is None:
        backend = UsfmParserBackend()
    sfmproc = UsfmGrammarParser(rdoc, backend)
    if start is None:
        start = "Scripture"
    parser = sfmproc.parseRef(start)
    return parser

def usfmGrammar(gsrc, extensions=[], altparser=False, backend=None, start=None, **kw):
    """ Create UsfmGrammarParser from gsrc as used by USX.fromUsfm """
    if altparser:
        rdoc = _grammarDoc(gsrc, extensions)
        return _usfmGrammar(rdoc, backend, start)
    else:
        res = Grammar()
        if len(extensions):
            for e in extensions:
                res.readmrkrs(e)
        return res

filetypes = {".xml": "usx", ".usx": "usx", ".usfm": "usfm", ".sfm": "usfm3.0", ".json": "usj", ".usj": "usj", ".txt": "usfm3.0"}

def readFile(infpath, informat=None, gramfile=None, grammar=None, extfiles=None, altparser=False, strict=False, keepparser=False, **kw):
    """ Reads a USFM file of a given type or inferred from the filename
        extension. extfiles allows for extra markers.ext files to extend the grammar"""
    if informat is None:
        inroot, ext = os.path.splitext(infpath)
        intype = filetypes.get(ext.lower(), informat)
    else:
        intype = informat
    if intype is None:
        return None
    if extfiles is None:
        extfiles = []

    if altparser and grammar is None:
        if gramfile is None:
            for a in ([], ['..', '..', '..', 'grammar']):
                gramfile = os.path.join(os.path.dirname(__file__), *a, "usx.rng")
                if os.path.exists(gramfile):
                    break
    if grammar is None:
        fname = getattr(infpath, 'name', infpath)
        extfiles.append(os.path.join(os.path.dirname(fname), "markers.ext"))
        exts = [x for x in extfiles if os.path.exists(x) or hasattr(x, 'read')]
        grammar = usfmGrammar(gramfile, extensions=exts, altparser=altparser, **kw)

    if intype == "usx":
        usxdoc = USX.fromUsx(infpath, grammar=grammar, **kw)
    elif intype == "usj":
        usxdoc = USX.fromUsj(infpath, grammar=grammar, **kw)
    elif intype.startswith("usfm"):
        usxdoc = USX.fromUsfm(infpath, grammar=grammar, altparser=altparser, strict=strict, keepparser=keepparser, **kw)
    return usxdoc


class USX:
    @classmethod
    def fromUsx(cls, src, elfactory=None, grammar=None, **kw):
        """ Loads USX and creates USX object to hold it """
        if elfactory is None:
            elfactory = ParentElement
        tb = et.TreeBuilder(element_factory=elfactory)
        parser = et.XMLParser(target=tb)
        if isinstance(src, str) and os.path.exists(src):
            inf = open(src, encoding="utf_8_sig")
        else:
            inf = src
        if hasattr(inf, "read"):
            anet = et.ElementTree()
            anet.parse(inf, parser=parser)
            res = anet.getroot()
            if src != inf:
                inf.close()
        else:
            try:
                res = et.fromstring(src, parser=parser)
            except et.ParseError:
                return None
        return cls(res, grammar)

    @classmethod
    def fromUsfm(cls, src, grammar=None, altparser=False, elfactory=None, timeout=1e7, strict=False, keepparser=False, version="3.1", preprocess=None, **kw):
        """ Parses USFM using UsfmGrammarParser grammar and creates USX object.
            Raise usfmtc.parser.NoParseError on error.
            elfactory must take parent and pos named parameters not as attributes
            preprocess, if given, is applied to the USFM text before it is parsed
        """
        readerr = None
        try:
            data = readsrc(src, errors='strict')
        except UnicodeError as e:
            readerr = f"In file {getSrcName(src)}: {e}"
            data = readsrc(src)
        if preprocess is not None:
            data = preprocess(data)
        if isinstance(version, str):
            version = [int(x) for x in version.split(".")]

        if not altparser:
            p = USFMParser(data, factory=elfactory or ParentElement, grammar=grammar, strict=strict, version=version, **kw)
            xml = p.parse()
        else:
            # This can raise usfmtc.parser.NoParseError
            p = None
            result = parseusfm(data, grammar, timeout=timeout, isdata=True, **kw)
            xml = result.asEt(elfactory=elfactory)

        if p and readerr is not None:
            p.errors.insert(0, (readerr,))
        cleanup(xml)            # normalize space, de-escape chars, cell aligns, etc.
        res = cls(xml, grammar, errors=p.errors if p else None, version=getattr(p, 'version', None))
        if keepparser:
            res.parser = p
        return res

    @classmethod
    def fromUsj(cls, src, elfactory=None, grammar=None, **kw):
        data = readsrc(src, errors=kw.get("errors", "replace"))
        djson = json.loads(data)
        xml = usjtousx(djson, elfactory=elfactory)
        return cls(xml, grammar)

    def __init__(self, xml, grammar=None, errors=None, version=None):
        self.xml = xml      # an Element, not an ElementTree
        self.grammar = grammar
        if self.grammar is None:
            self.grammar = Grammar()
        self.errors = errors    # list of errors (description, sfmparser.Pos)
        if version is not None:
            self.version = version

    def copy(self, deep=False):
        res = self.__class__(self.xml.copy(deep=deep), grammar=self.grammar)
        return res

    def _outwrite(self, file, dat, fn=None, args={}):
        if fn is None:
            fn = lambda f, d: f.write(d)
        if file is None:
            fh = io.StringIO()
            fn(fh, dat, **args)
            res = fh.getvalue()
            fh.close()
            return res
        if not hasattr(file, "read"):
            fh = open(file, "w", encoding="utf-8")
            fn(fh, dat, **args)
            fh.close()
        else:
            fn(file, dat, **args)
        return True

    def outUsx(self, file=None, **kw):
        """ Output pretty XML USX. If file is None returns string """
        if self.xml is None:
            return None
        prettyxml(self.xml)
        return self._outwrite(file, self.xml, fn=writexml)

    def outUsfm(self, file=None, grammar=None, altparser=False, version=None, **kw):
        """ Output USFM from USX object. grammar is et doc. If file is None returns string """
        if not altparser:
            if isinstance(version, str):
                version = [int(x) for x in version.split(".")]
            if version is not None:
                kw['version'] = version
            if grammar is None:
                grammar = self.grammar
            if 'book' not in kw:
                kw['book'] = self.book
            return self._outwrite(file, self.xml, fn=usx2usfm, args={'grammar': grammar, **kw})
        parser = USXConverter(grammar.getroot(), **kw)
        res = parser.parse(self.xml)
        if res:
            dat = "".join(res.results)
            return self._outwrite(file, dat)
        return False

    def outUsj(self, file=None, ensure_ascii=False, **kw):
        """ Output USJ from USX object. If file is None returns dict """
        res = usxtousj(self.xml)
        v = ".".join([str(x) for x in self.version]) if self.version is not None else None
        if res.get('version', None) != v:
            res['version'] = v
        if file is None:
            return res
        else:
            dat = json.dumps(res, indent=2, ensure_ascii=ensure_ascii)
            self._outwrite(file, dat)

    def getroot(self):
        """ Returns root XML element """
        return self.xml

    def _procrefs(self, *refs, skiptest=None):
        for r in refs:
            if r.first.book is not None and r.first.book != self.book:
                continue
            start = USXCursor.fromRef(r.first, self, skiptest=skiptest)
            end = USXCursor.fromRef(r.last, self, atend=True, skiptest=skiptest)
            yield start, end, r

    def getrefs(self, *refs, addintro=False, titles=True, skiptest=None, headers=True, chapters=True, vid=None):
        """ Returns a doc containing paragraphs of the contents of each reference.
            skiptest is a fn to test whether text in the marker does not cause
            a word break. addintro includes material before chapter 1, including titles.
            titles includes material up to the first introductory material. headers includes
            any section headers occurring immediately before a reference. chapters
            says whether to include preceding chapter at the start of a range if v 1. """
        root = self.getroot()
        res = root.__class__(root.tag, attrib=root.attrib)
        books = set()
        for i, (start, end, r) in enumerate(self._procrefs(*refs, skiptest=skiptest)):
            subdoc = start.copy_range(root, end, addintro=(addintro and r.first.book not in books),
                                      titles=titles and not i, headers=headers, vid=r.first,
                                      chapters=chapters, grammar=self.grammar)
            if len(subdoc):
                for e in subdoc:
                    e.parent = res
                    res.append(e)
            books.add(r.first.book)
        res.insert(0, root[0].copy(deep=True, parent=res))
        return self.__class__(res, grammar=self.grammar)

    def gettext(self, *refs, skiptest=None, notes=False):
        """ Returns the text of each reference one per line. skiptest is a fn
            to test whether text in the marker does not cause a word break. """
        root = self.getroot()
        res = []
        for (start, end, r) in self._procrefs(*refs, skiptest=skiptest):
            text = start.copy_text(root, end, notes=notes, grammar=self.grammar)
            res.append(text)
        return "\n".join(res)

    def iterusx(self, refs=False, **kw):
        """ Iterates the doc root yielding a node and whether we are in or after (isin) the node.
            If refs is True also yield a third value of a current reference. Once until is hit,
            iteration stops. The node matching until is entered if untilafter is True
            otherwise it is not yielded.  blocks prunes any node whose
            style has a category listed in blocks. The test is inverted if unblocks is True.
            filt is a list of functions that all must pass for the value to be yielded.
            until may be a function that tests a node for it being the last node. """
        f = iterusxref if refs else iterusx
        return f(self.getroot(), **kw)

    def reversify(self, srcvrs, tgtvrs, **kw):
        """ Change versification of this text from the srcvrs object to the
            tgtvrs object: e.g. Versification("eng.vrs") """
        if srcvrs is None:
            srcvrs, tgtvrs = tgtvrs, srcvrs
            rev = True
        else:
            rev = False
        reversify(self, srcvrs, tgtvrs, reverse=rev, **kw)

    def saveAs(self, outfpath, outformat=None, addesids=False, grammar=None,
                gramfile=None, version=None, altparser=False, **kw):
        """ Saves the document to a file in the appropriate format, either given
            or inferred from the filename extension. """
        if outformat is None:
            outroot, ext = os.path.splitext(outfpath)
            outtype = filetypes.get(ext.lower(), outformat)
        else:
            outtype = outformat
        if outtype is None:
            return

        if outtype == "usx":
            if addesids:
                self.addesids()
            return self.outUsx(outfpath, **kw)
        elif outtype == "usj":
            return self.outUsj(outfpath, **kw)
        elif outtype == "usfm":
            if outtype == "usfm3.0":
                outtype = "usfm"
                if version is None:
                    version = "3.0"
            return self.outUsfm(grammar=grammar, file=outfpath, outversion=version, altparser=altparser, **kw)

    def canonicalise(self, version=None):
        """ Canonicalises the text especially with regard to whitespace """
        canonicalise(self.getroot(), version=version)
        if version is not None:
            self.version = version

    def regularise(self, ptx=False):
        """ Further edits to fix common mistakes that may not need fixing in all files:
                - Ensure space before verse
                - Ensure verses have a paragraph as parent by closing and opening
                  the char styles
                - if ptx, then set refs to gen="1" and closed="false" on note char styles
                - clear out empty char styles and par styles
        """
        regularise(self.getroot(), ptx=ptx, grammar=self.grammar)
        clear_empties(self.getroot(), ptx=ptx, grammar=self.grammar)

    def addesids(self):
        """ Add esids to USX object (eid, sids, vids) """
        addesids(self.xml)

    def addorncv(self):
        """ Adds CV info to node.pos throughout the doc """
        if getattr(self, "addorned", False):
            return
        self.bridges = addorncv(self.getroot(), grammar=self.grammar)
        self.addorned = True

    def addindexes(self):
        """ Creates self.chapter a list of chapter nodes and self.ids, a
            dictionary of ids to nodes (e.g. "a.intro") """
        self.chapters, self.ids = addindexes(self.xml)

    @property
    def version(self):
        res = self.getroot().get('version', None)
        if res is not None:
            res = [int(x) for x in res.split(".")]
        return res

    @version.setter
    def version(self, version):
        if isinstance(version, (list, tuple)):
            version = ".".join([str(x) for x in version])
        if version is not None:
            self.getroot().set('version', str(version))

    @property
    def book(self):
        bke = self.getroot().find(".//book")
        if bke is not None:
            return bke.get("code", None)
        return None

    @book.setter
    def book(self, code):
        bke = self.getroot().find(".//book")
        if bke is not None:
            bke.set('code', code)


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
