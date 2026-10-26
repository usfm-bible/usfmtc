#!/usr/bin/env python3

# nuitka configuration
# nuitka-project: --onefile
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/usx.rng=usx.rng
# nuitka-project-if: {OS} in ("Windows",):
#     nuitka-project: --output-filename=usfmconv.exe
# nuitka-project-else:
#     nuitka-project: --output-filename=usfmconv.bin

""" usfmconv: converts between USFM, USX and USJ """

import os
from usfmtc.usfm import readFile, usfmGrammar, _grammarDoc, _filetypes
from usfmtc.validating.rngparser import NoParseError
from usfmtc.reference import RefList
from usfmtc.versification import cached_versification

def main(hookcli=None, hookusx=None, argv=None):

    import argparse, logging, sys
    from glob import glob

    parser = argparse.ArgumentParser()
    parser.add_argument("infile",nargs="+",help="Input file(s) supports wildcards, or directories of *sfm files")
    parser.add_argument("-o", "--outfile",help="Output file or directory, with inferred format")
    parser.add_argument("-F","--outformat",help="Output format [usfm, usx, usj, usfm3.0] if not inferrable")
    parser.add_argument("-I","--informat",help="Input format [usfm, usx, usj] if not inferrable")
    parser.add_argument("-x","--extfiles",action="append",default=[],help="markers.ext files to include (repeatable)")
    parser.add_argument("-g","--grammar",help="Grammar file to use, if needed")
    parser.add_argument("-R","--refs",action="append",default=[],help="Extract a reference list (repeatable)")
    parser.add_argument("--intro",action="store_true",default=False,help="Include intro material before references output")
    parser.add_argument("-f","--from",dest="fromvrs",help="Versification of the input (.vrs file or name, e.g. eng), "
                        "to change from it to org or --to")
    parser.add_argument("-t","--to",dest="tovrs",help="Versification to change the text to (.vrs file or name), "
                        "from org or --from")
    parser.add_argument("-k","--keep",action="store_true",help="When changing versification, add \\vp for changed verse numbers")
    parser.add_argument("--vpchap",action="store_true",help="With --keep, include chapter numbers if different")
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
    args = parser.parse_args(argv)

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
        infiles = []
        for x in args.infile:
            if os.path.isdir(x):
                infiles.extend(sorted(os.path.join(x, f) for f in os.listdir(x) if f.lower().endswith("sfm")))
            else:
                infiles.extend(glob(x))
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

    def _getvrs(v):
        if v is None:
            return None
        res = cached_versification(v)
        if res is None:
            doerror(f"Can't find versification {v}")
        return res

    fromvrs = _getvrs(args.fromvrs)
    tovrs = _getvrs(args.tovrs)

    reflist = None
    if len(args.refs):
        reflist = sum((RefList(r) for r in args.refs), [])

    for infile in infiles:
        outfile = None
        if args.outfile is None:
            outfile = _makeoutfile(infile, args.outformat)
        elif os.path.isdir(args.outfile):
            outf = _makeoutfile(infile, args.outformat) if args.outformat else infile
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

        if usxdoc.errors is not None and len(usxdoc.errors):
            for m, p, r in usxdoc.errors:
                doerror(f"{r} ({p}): {m}", False)

        if reflist is not None:
            book = usxdoc.book
            bkrefs = [r for r in reflist if r.first.book == book]
            usxdoc = usxdoc.getrefs(*bkrefs, addintro=args.intro, headers=True)

        if fromvrs is not None or tovrs is not None:
            usxdoc.reversify(fromvrs, tovrs, keep=args.keep, chnums=args.vpchap)

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
