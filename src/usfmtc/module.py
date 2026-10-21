""" Paratext module flattener.

A module is a USFM document containing \\m... milestones and $ expressions.
The Module class walks a parsed module document and expands its contents
into plain USFM/USX.
"""

import re, inspect
from typing import Optional, Dict, List, Union
from usfmtc.reference import RefList, Environment


class ModuleError(Exception):
    pass


class Result:
    """ A node in a parsed expression: literal text, a quoted literal or a parse error """
    TEXT, QUOTED, ERROR, CALL, VAR = range(5)

    def __init__(self, s: str, kind: int = TEXT):
        self.s = s
        self.kind = kind

    def __repr__(self):
        return f"Result({self.s!r}, {self.kind})"

    def istext(self):
        return self.kind == self.TEXT

    def isquoted(self):
        return self.kind == self.QUOTED

    def isliteral(self):
        """ Text that is output as is, quoted or not """
        return self.kind in (self.TEXT, self.QUOTED)

    def iserror(self):
        return self.kind == self.ERROR

    def iscall(self):
        return self.kind == self.CALL

    def isvar(self):
        return self.kind == self.VAR

    def isempty(self):
        return self.istext() and not self.s

    def lstrip(self):
        """ Whitespace around unquoted text is insignificant """
        return Result(self.s.lstrip()) if self.istext() else self

    def rstrip(self):
        return Result(self.s.rstrip()) if self.istext() else self


class _Call(Result):
    """ A $name(...) function call. Each argument is a list of nodes. """
    def __init__(self, name: str, args: List[List[Result]], start: int, end: int):
        super().__init__(name, self.CALL)
        self.name = name
        self.args = args
        self.start = start
        self.end = end

    def __repr__(self):
        return f"Call({self.name}, {self.args!r})"


def modulefn(name: str):
    """ Registers a method as the implementation of the module function $name """
    def deco(fn):
        fn._modulefn = name
        return fn
    return deco


class Module:
    """ Flattens a parsed module document.

        doc is a USX object as read by usfmtc. envs maps language tags to reference
        Environments (e.g. BookNamesEnvironment) used to localise references;
        the "*" entry is the fallback. lang is the default language. variables
        gives initial global variables: name -> value, where a value is a string
        (its "*" form) or a dict of language tag -> string. """

    errorfmt = "[ERROR: {}]"
    _namere = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    def __init__(self, doc, envs: Optional[Dict[str, Environment]] = None, lang: str = "*",
                 variables: Optional[Dict[str, Union[str, Dict[str, str]]]] = None):
        self.doc = doc
        self.envs = envs or {}
        self.lang = lang
        self.frames = [{}]          # variable frames, global first: name -> {lang: value}
        for k, v in (variables or {}).items():
            self.frames[0][k] = dict(v) if isinstance(v, dict) else {"*": v}
        self.errors = []
        self.functions = {}
        for k in dir(self.__class__):
            v = getattr(self.__class__, k)
            if callable(v) and hasattr(v, "_modulefn"):
                self.functions[v._modulefn] = getattr(self, k)

    def flatten(self):
        """ Returns a copy of the document with its contents expanded """
        res = self.doc.copy(deep=True)
        for e in res.getroot().iter():
            if e.text:
                e.text = self.expand(e.text, e)
            if e.tail:
                e.tail = self.expand(e.tail, e)
            for k, v in e.attrib.items():
                e.set(k, self.expand(v, e))
        return res

    def expand(self, s: str, e=None) -> str:
        """ Expands a content string. Each top level expansion that fails is replaced
            by an error marker and the error recorded. """
        res = []
        for n in self._parse(s, 0, "")[0]:
            if n.isliteral():
                res.append(n.s)
                continue
            try:
                if n.iserror():
                    raise ModuleError(n.s)
                res.append(self._eval(n))
            except ModuleError as err:
                self.errors.append((str(err), getattr(e, "pos", None)))
                res.append(self.errorfmt.format(err))
        return "".join(res)

    def _eval(self, n) -> str:
        if n.isliteral():
            return n.s
        if n.isvar():
            if self._findvar(n.s) is None:
                return "$" + n.s            # not a variable, so literal
            return self.getvar(n.s)
        fn = self.functions[n.name]
        args = ["".join(self._eval(x) for x in a) for a in n.args]
        try:
            inspect.signature(fn).bind(*args)
        except TypeError:
            raise ModuleError(f"Wrong number of arguments ({len(args)}) to ${n.name}")
        return fn(*args)

    def _parse(self, s: str, i: int, stops: str):
        """ Parses s from i until an unquoted character in stops (or the end).
            Returns (nodes, index of the stop character). """
        nodes = []
        text = []
        def flush():
            if text:
                nodes.append(Result("".join(text)))
                text.clear()
        while i < len(s):
            c = s[i]
            if c in stops:
                break
            if c in "\"'" and stops and not nodes and not "".join(text).strip():
                # quoted literal at the start of an argument
                j = s.find(c, i+1)
                if j < 0:
                    raise ModuleError(f"Unterminated quote in {s}")
                text.clear()
                nodes.append(Result(s[i+1:j], Result.QUOTED))
                i = j + 1
                continue
            if c != "$":
                text.append(c)
                i += 1
                continue
            nxt = s[i+1:i+2]
            if nxt == "$":
                text.append("$")
                i += 2
            elif s.startswith("${}", i):
                i += 3
            elif nxt == "#":
                j = s.find("\n", i)
                i = len(s) if j < 0 else j
            elif (m := self._namere.match(s, i+1)):
                flush()
                if m.group(0) in self.functions and s[m.end():m.end()+1] == "(":
                    try:
                        call, i = self._parsecall(s, m.group(0), i, m.end() + 1)
                    except ModuleError as err:
                        if stops:
                            raise
                        call, i = Result(str(err), Result.ERROR), len(s)   # a top level syntax error consumes the rest
                    nodes.append(call)
                else:
                    nodes.append(Result(m.group(0), Result.VAR))
                    i = m.end()
            else:                               # unrecognised $ is literal
                text.append("$")
                i += 1
        flush()
        return nodes, i

    def _parsecall(self, s: str, name: str, start: int, i: int):
        """ Parses the argument list of a call; i is just after the '('. """
        args = []
        if (m := re.compile(r"\s*\)").match(s, i)):
            return _Call(name, args, start, m.end()), m.end()
        while True:
            arg, i = self._parse(s, i, ",)")
            args.append(self._stripws(arg))
            if i >= len(s):
                raise ModuleError(f"Missing ) in call to ${name}")
            i += 1
            if s[i-1] == ")":
                return _Call(name, args, start, i), i

    @staticmethod
    def _stripws(arg):
        """ Whitespace around an argument is insignificant """
        if arg:
            arg[0] = arg[0].lstrip()
            arg[-1] = arg[-1].rstrip()
        return [a for a in arg if not a.isempty()]

    def _findvar(self, name: str) -> Optional[Dict[str, str]]:
        """ Returns the forms of the innermost binding of name, or None """
        for f in reversed(self.frames):
            if name in f:
                return f[name]
        return None

    def getvar(self, name: str, lang: str = "*", default: Optional[str] = None) -> str:
        """ Reads a variable: the frame chain chooses the variable, then lang chooses
            its form: exact tag, else "*", else default """
        forms = self._findvar(name)
        if forms is not None:
            for k in (lang, "*"):
                if k in forms:
                    return forms[k]
        if default is None:
            raise ModuleError(f"No value for ${name}" + (f" in {lang}" if lang != "*" else ""))
        return default

    def _env(self, lang: Optional[str]) -> Environment:
        lang = lang or self.lang
        env = self.envs.get(lang, self.envs.get("*", None))
        if env is None:
            raise ModuleError(f"No reference environment for language {lang}")
        return env

    def _localref(self, ref: str, level: int, lang: Optional[str]) -> str:
        env = self._env(lang)
        try:
            refs = RefList(ref, env=env)
        except SyntaxError as err:
            raise ModuleError(f"Bad reference {ref!r}: {err}")
        if not len(refs):
            raise ModuleError("Empty reference")
        return refs.str(env=env, level=level)

    @modulefn("s")
    def fn_s(self, ref, lang=None):
        """ $s(ref, [lang]): short localised form of a reference """
        return self._localref(ref, 1, lang)


def main(argv=None):
    import argparse, sys, os
    from usfmtc import readFile
    from usfmtc.reference import BookNamesEnvironment

    parser = argparse.ArgumentParser(description="Flatten a Paratext module into plain USFM/USX")
    parser.add_argument("infile", help="Input module file")
    parser.add_argument("outfile", help="Output file, format inferred from extension")
    parser.add_argument("-b", "--booknames", help="BookNames.xml for localising references")
    parser.add_argument("-l", "--lang", default="*", help="Default language")
    parser.add_argument("-x", "--extfiles", action="append", default=[],
                        help="markers.ext files to include (repeatable)")
    parser.add_argument("-D", "--define", action="append", default=[],
                        help="Set a global variable name[:lang]=value (repeatable)")
    args = parser.parse_args(argv)

    doc = readFile(args.infile, extfiles=args.extfiles)
    if doc is None:
        parser.error(f"Can't read {args.infile}")
    env = BookNamesEnvironment(args.booknames) if args.booknames else Environment()
    variables = {}
    for d in args.define:
        k, v = d.split("=", 1)
        name, _, lang = k.partition(":")
        variables.setdefault(name, {})[lang or "*"] = v
    mod = Module(doc, envs={"*": env}, lang=args.lang, variables=variables)
    res = mod.flatten()
    res.saveAs(args.outfile)
    for msg, pos in mod.errors:
        print(f"{args.infile}:{pos}: {msg}" if pos is not None else f"{args.infile}: {msg}", file=sys.stderr)
    return 1 if mod.errors else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
