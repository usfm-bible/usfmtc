""" usfmmodule: flattens a Paratext module into plain USFM/USX """

import argparse, sys, os
from usfmtc.module import ModuleFatalError, flattenModuleFile


def main(argv=None):

    parser = argparse.ArgumentParser(description="Flatten a Paratext module into plain USFM/USX")
    parser.add_argument("infile", help="Input module file")
    parser.add_argument("outfile", help="Output file, format inferred from extension")
    parser.add_argument("-p", "--project", help="Project (directory name) to flatten the module in")
    parser.add_argument("-R", "--root", action="append", default=[],
                        help="Directory of projects (repeatable, default: the current directory)")
    parser.add_argument("-b", "--booknames", help="BookNames.xml for localising references, "
                        "instead of the project's")
    parser.add_argument("-l", "--lang", help="Module language, instead of the project's ($LANG starts as this)")
    parser.add_argument("-C", "--ldmldir", help="Directory of cached flattened LDML files for $ldml "
                        "(default the user's cache)")
    parser.add_argument("--refresh-ldml", action="store_true", help="Fetch the LDML files for $ldml again")
    parser.add_argument("-x", "--extfiles", action="append", default=[],
                        help="markers.ext files to include (repeatable)")
    parser.add_argument("-D", "--define", action="append", default=[],
                        help="Set a global variable name[:lang]=value (repeatable)")
    args = parser.parse_args(argv)

    variables = {}
    for d in args.define:
        k, v = d.split("=", 1)
        name, _, lang = k.partition(":")
        variables.setdefault(name, {})[lang or "*"] = v
    errors = []
    try:
        res = flattenModuleFile(args.infile, project=args.project, projects=args.root or [os.getcwd()],
                                lang=args.lang, booknames=args.booknames, variables=variables,
                                moderrors=errors, extfiles=args.extfiles,
                                ldmldir=args.ldmldir, refreshldml=args.refresh_ldml)
    except ValueError as err:
        parser.error(str(err))
    except ModuleFatalError as err:
        print(f"{args.infile}: {err}", file=sys.stderr)
        return 2
    res.saveAs(args.outfile)
    for msg, line in errors:
        fname = args.infile
        if getattr(line, "file", None):     # in an included file
            fname, line = os.path.join(os.path.dirname(args.infile), line.file), int(line)
        print(f"{fname}:{line}: {msg}" if line is not None else f"{fname}: {msg}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
