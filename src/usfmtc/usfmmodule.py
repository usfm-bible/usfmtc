""" usfmmodule: flattens a Paratext module into plain USFM/USX """

import argparse, sys, os
from usfmtc.module import Module, ModuleFatalError, readModule
from usfmtc.reference import BookNamesEnvironment, Environment
from usfmtc.projects import Projects


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
    parser.add_argument("-x", "--extfiles", action="append", default=[],
                        help="markers.ext files to include (repeatable)")
    parser.add_argument("-D", "--define", action="append", default=[],
                        help="Set a global variable name[:lang]=value (repeatable)")
    args = parser.parse_args(argv)

    doc = readModule(args.infile, extfiles=args.extfiles)
    if doc is None:
        parser.error(f"Can't read {args.infile}")
    projects = Projects(*(args.root or [os.getcwd()]))
    project = None
    if args.project:
        project = projects.findProject(args.project)
        if project is None:
            parser.error(f"No project {args.project} in {', '.join(projects.treedirs)}")
    envs = {}
    if args.booknames:
        envs[args.lang or (project.lang if project is not None else "*")] = BookNamesEnvironment(args.booknames)
    envs.setdefault("*", Environment())
    variables = {}
    for d in args.define:
        k, v = d.split("=", 1)
        name, _, lang = k.partition(":")
        variables.setdefault(name, {})[lang or "*"] = v
    mod = Module(doc, envs=envs, lang=args.lang, variables=variables, project=project, projects=projects)
    try:
        res = mod.flatten()
    except ModuleFatalError as err:
        print(f"{args.infile}: {err}", file=sys.stderr)
        return 2
    res.saveAs(args.outfile)
    for msg, line in mod.errors:
        print(f"{args.infile}:{line}: {msg}" if line is not None else f"{args.infile}: {msg}", file=sys.stderr)
    return 1 if mod.errors else 0


if __name__ == "__main__":
    sys.exit(main())
