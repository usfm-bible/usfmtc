#!/usr/bin/env python3

# nuitka configuration
# nuitka-project: --onefile
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/usx.rng=usx.rng
# nuitka-project-if: {OS} in ("Windows",):
#     nuitka-project: --output-filename=usfmconv.exe
# nuitka-project-else:
#     nuitka-project: --output-filename=usfmconv.bin

import os, json, io
from usfmtc.utils import readsrc
from usfmtc.validating.usfmparser import parseusfm, UsfmParserBackend
from usfmtc.validating.rngparser import NoParseError
from usfmtc.extension import Extensions
from usfmtc.xmlutils import ParentElement, prettyxml, writexml
from usfmtc.validating.usxparser import USXConverter
from usfmtc.validating.usfmgrammar import UsfmGrammarParser
from usfmtc.usxmodel import addesids, cleanup, canonicalise, reversify, iterusx, regularise, addorncv
from usfmtc.usxcursor import USXCursor
from usfmtc.usjproc import usxtousj, usjtousx
from usfmtc.usfmparser import USFMParser, Grammar
from usfmtc.usfmgenerate import usx2usfm
from usfmtc.reference import RefList
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

_filetypes = {".xml": "usx", ".usx": "usx", ".usfm": "usfm", ".sfm": "usfm3.0", ".json": "usj", ".usj": "usj"}

def readFile(infpath, informat=None, gramfile=None, grammar=None, extfiles=None, altparser=False, strict=False, keepparser=False, **kw):
    """ Reads a USFM file of a given type or inferred from the filename
        extension. extfiles allows for extra markers.ext files to extend the grammar"""
    if informat is None:
        inroot, ext = os.path.splitext(infpath)
        intype = _filetypes.get(ext.lower(), informat)
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
    def fromUsfm(cls, src, grammar=None, altparser=False, elfactory=None, timeout=1e7, strict=False, keepparser=False, **kw):
        """ Parses USFM using UsfmGrammarParser grammar and creates USX object.
            Raise usfmtc.parser.NoParseError on error.
            elfactory must take parent and pos named parameters not as attributes
        """
        data = readsrc(src)

        if not altparser:
            p = USFMParser(data, factory=elfactory or ParentElement, grammar=grammar, strict=strict, **kw)
            xml = p.parse()
        else:
            # This can raise usfmtc.parser.NoParseError
            p = None
            result = parseusfm(data, grammar, timeout=timeout, isdata=True, **kw)
            xml = result.asEt(elfactory=elfactory)

        cleanup(xml)            # normalize space, de-escape chars, cell aligns, etc.
        res = cls(xml, grammar, errors=p.errors if p else None)
        if keepparser:
            res.parser = p
        return res

    @classmethod
    def fromUsj(cls, src, elfactory=None, grammar=None, **kw):
        data = readsrc(src)
        djson = json.loads(data)
        xml = usjtousx(djson, elfactory=elfactory)
        return cls(xml, grammar)

    def __init__(self, xml, grammar=None, errors=None):
        self.xml = xml      # an Element, not an ElementTree
        self.grammar = grammar
        if self.grammar is None:
            self.grammar = Grammar()
        self.errors = errors    # list of errors (description, sfmparser.Pos)

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

    def outUsfm(self, file=None, grammar=None, altparser=False, **kw):
        """ Output USFM from USX object. grammar is et doc. If file is None returns string """
        if not altparser:
            if grammar is None:
                grammar = Grammar()
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
        return self.__class__(res, grammar=self.grammar)

    def gettext(self, *refs, skiptest=None):
        """ Returns the text of each reference one per line. skiptest is a fn
            to test whether text in the marker does not cause a word break. """
        root = self.getroot()
        res = []
        for (start, end, r) in self._procrefs(*refs, skiptest=skiptest):
            text = start.copy_text(root, end)
            res.append(text)
        return "\n".join(res)

    def iterusx(self, **kw):
        """ Iterates the doc root yielding a node and whether we are in or after (isin) the node. Once until is hit,
            iteration stops. The node matching until is entered if untilafter is True
            otherwise it is not yielded.  blocks prunes any node whose
            style has a category listed in blocks. The test is inverted if unblocks is True.
            filt is a list of functions that all must pass for the value to be yielded.
            until may be a function that tests a node for it being the last node. """
        return iterusx(self.getroot(), **kw)

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
            outtype = _filetypes.get(ext.lower(), outformat)
        else:
            outtype = outformat
        if outtype is None:
            return

        if outtype == "usx":
            if addesids:
                self.addesids()
            self.outUsx(outfpath, **kw)
        elif outtype == "usj":
            self.outUsj(outfpath, **kw)
        elif outtype == "usfm":
            if outtype == "usfm3.0":
                outtype = "usfm"
                if version is None:
                    version = "3.0"
            self.outUsfm(grammar=grammar, file=outfpath, outversion=version, altparser=altparser, **kw)

    def canonicalise(self, version=None):
        """ Canonicalises the text especially with regard to whitespace """
        canonicalise(self.getroot(), version=version)
        if version is not None:
            self.version = version

    def regularise(self):
        """ Further edits to fix common mistakes that may not need fixing in all files:
                - Ensure space before verse
        """
        regularise(self.getroot())

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

def main(hookcli=None, hookusx=None):

    import argparse, logging, sys
    from glob import glob

    parser = argparse.ArgumentParser()
    parser.add_argument("infile",nargs="+",help="Input file(s) supports wildcards")
    parser.add_argument("-o", "--outfile",help="Output file or directory, with inferred format")
    parser.add_argument("-F","--outformat",help="Output format [usfm, usx, usj, usfm3.0] if not inferrable")
    parser.add_argument("-I","--informat",help="Input format [usfm, usx, usj] if not inferrable")
    parser.add_argument("-x","--extfiles",action="append",default=[],help="markers.ext files to include (repeatable)")
    parser.add_argument("-g","--grammar",help="Grammar file to use, if needed")
    parser.add_argument("-R","--refs",action="append",default=[],help="Extract a reference list (repeatable)")
    parser.add_argument("--intro",action="store_true",default=False,help="Include intro material before references output")
    parser.add_argument("-e","--esids",action="store_true",
                        help="Add esids, vids, sids, etc. to USX output")
    parser.add_argument("-S","--strict",action="store_true",default=False,help="Be strict in parsing")
    parser.add_argument("-v","--version",default=None,help="Set USFM version [3.1]")
    parser.add_argument("-V","--validate",action="store_true",default=False,help="Use validating parser for USFM")
    parser.add_argument("-C","--canonical",action="store_true",help="Do not canonicalise")
    parser.add_argument("-A","--ascii",action="store_true",help="Output as ASCII only in json")
    parser.add_argument("-l","--logging",help="Set logging level to usfmxtest.log")
    parser.add_argument("-q","--quiet",action="store_true",help="Don't say much")
    parser.add_argument("--nooutput",action="store_true",help="Don't output any data")
    if hookcli is not None:
        hookcli(parser)
    args = parser.parse_args()

    if args.logging:
        try:
            loglevel = int(args.logging)
        except ValueError:
            loglevel = getattr(logging, args.logging.upper(), None)
        if isinstance(loglevel, int):
            parms = {'level':  loglevel, 'datefmt': '%d/%b/%Y %H:%M:%S',
                     'format': '%(asctime)s.%(msecs)03d %(levelname)s:%(module)s(%(lineno)d) %(message)s'}
            logfh = open("usfmconv.log", "w", encoding="utf-8")
            parms.update(stream=logfh, filemode="w") #, encoding="utf-8")
            try:
                logging.basicConfig(**parms)
            except FileNotFoundError as e:      # no write access to the log
                print("Exception", e)
        log = logging.getLogger('usfmconv')
    else:
        log = None

    def doerror(msg, doexit=True):
        if log:
            log.error(msg)
        if not args.quiet:
            print(msg)
        if doexit:
            sys.exit(1)
    
    fileexts = {"usx": ".xml", "usfm": ".usfm", "usj": ".json"}

    def _makeoutfile(infile, oformat):
        outext = fileexts.get(oformat, None)
        inroot, ext = os.path.splitext(infile)
        return inroot + outext if outext else None
    
    if args.infile == ["-"]:
        infiles = args.infile
    else:
        infiles = sum((glob(x) for x in args.infile), [])
    if not len(infiles):
        doerror(f"No files found in {args.infile}")

    root, ext = os.path.splitext(infiles[0])
    args.informat = args.informat or _filetypes.get(ext.lower(), args.informat)
    if args.outformat is None:
        if args.outfile is not None and not os.path.isdir(args.outfile):
            root, ext = os.path.splitext(args.outfile)
            args.outformat = _filetypes.get(ext.lower(), None)
    ingrammar = None
    outgrammar = None
    if (args.informat and args.informat.startswith("usfm")) or (args.outformat and args.outformat.startswith("usfm")):
        if args.validate and args.grammar is None:
            doerror(f"A validating parser generator requires a --grammar RNG file")
            return
        if args.informat.startswith("usfm"):
            args.extfiles.append(os.path.join(os.path.dirname(infiles[0]), "markers.ext"))
            exts = [x for x in args.extfiles if os.path.exists(x)]
            ingrammar = usfmGrammar(args.grammar, altparser=args.validate, extensions=exts)
        if args.outformat and args.outformat.startswith("usfm"):
            outgrammar = _grammarDoc(args.grammar)

    reflist = None
    if len(args.refs):
        reflist = sum((RefList(r) for r in args.refs), [])

    for infile in infiles:
        outfile = None
        if args.outfile is None:
            outfile = _makeoutfile(infile, args.outformat)
        elif os.path.isdir(args.outfile):
            outf = _makeoutfile(infile, args.outformat)
            if outf is None:
                doerror(f"invalid output format {args.outformat} in {args.outfile}")
            outfile = os.path.join(args.outfile, os.path.basename(outf))
        elif len(infiles) == 1:
            outfile = args.outfile

        if infile == "-":
            infile = sys.stdin
        if outfile == "-":
            outfile = sys.stdout

        usxdoc = None
        if not args.quiet:
            print(f"{infile} -> {outfile}" if outfile else f"{infile}")
        try:
            usxdoc = readFile(infile, informat=args.informat, grammar=ingrammar,
                              altparser=args.validate, strict=args.strict)
        except NoParseError as e:
            doerror(f"Failed to parse {infile}: {e}", False)
        except SyntaxError as e:
            doerror(f"{e}", False)

        if len(infiles) == 1 and usxdoc is None:
            doerror(f"Unable to read in {args.infile}")

        if reflist is not None:
            book = usxdoc.book
            bkrefs = [r for r in reflist if r.first.book == book]
            usxdoc = usxdoc.getrefs(*bkrefs, addintro=args.intro, headers=True)
            
        if hookusx is not None:
            hookusx(usxdoc, args)

        if args.nooutput or outfile is None or usxdoc is None:
            continue

        version = usxdoc.version
        if args.version is not None:
            usxdoc.version = args.version
        elif usxdoc.version is None:
            usxdoc.version = [3, 1]

        if not args.canonical:
            usxdoc.canonicalise()

        usxdoc.saveAs(outfile, outformat=args.outformat, addesids=args.esids,
                      grammar=outgrammar, altparser=args.validate, ensure_ascii=args.ascii)

if __name__ == "__main__":
    main()
