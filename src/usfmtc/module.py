""" Paratext module flattener.

A module is a USFM document containing \\m... milestones and $ expressions.
The Module class walks a parsed module document and expands its contents
into plain USFM/USX.
"""

import re, inspect, io
from typing import Optional, Dict, List, Union
from usfmtc.reference import RefList, Environment
from usfmtc.usfmgenerate import usx2usfm


class ModuleError(Exception):
    pass


class Result:
    """ A node in a parsed expression: literal text, a quoted literal or a parse error """
    TEXT, QUOTED, ERROR, CALL, VAR = range(5)

    def __init__(self, s: str, kind: int = TEXT, src: Optional[str] = None):
        self.s = s
        self.kind = kind
        self.src = src          # source text, where it differs from s

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


def modulems(name: str, end: Optional[str] = None):
    """ Registers a method as the handler of the module milestone \\name. It is
        passed the milestone element, whose attributes are not yet expanded. If
        end is given, \\name..\\end is a block and the element holds its contents. """
    def deco(fn):
        fn._modulems = name
        fn._modulemsend = end
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
        self.milestones = {}
        self.blocks = {}            # start milestone -> end milestone
        for k in dir(self.__class__):
            v = getattr(self.__class__, k)
            if not callable(v):
                continue
            if hasattr(v, "_modulefn"):
                self.functions[v._modulefn] = getattr(self, k)
            if hasattr(v, "_modulems"):
                self.milestones[v._modulems] = getattr(self, k)
                if v._modulemsend is not None:
                    self.blocks[v._modulems] = v._modulemsend

    def flatten(self):
        """ Returns a copy of the document with its contents expanded """
        res = self.doc.copy(deep=True)
        self._gather(res.getroot())
        self._walk(res.getroot())
        return res

    def _gather(self, root):
        """ Turns each block milestone pair into a single start milestone element
            holding the block's contents. Inner blocks are gathered first. """
        ends = set(self.blocks.values())
        stack = []
        pairs = []
        for e in root.iter("ms"):
            s = e.get("style", None)
            if s in self.blocks:
                stack.append(e)
            elif s in ends:
                if stack and self.blocks[stack[-1].get("style")] == s:
                    pairs.append((stack.pop(), e))
                else:
                    self.errors.append((f"Unexpected \\{s}", getattr(e, "pos", None)))
        for e in stack:
            self.errors.append((f"Missing \\{self.blocks[e.get('style')]}", getattr(e, "pos", None)))
        for s, e in pairs:
            self._gatherblock(root, s, e)

    @staticmethod
    def _gatherblock(root, start, end):
        """ Moves everything between start and end into start, removing end. Elements
            the block cuts across are split, and the part following end joins the
            element holding start, as if the block's text were not there. """
        parents = {c: p for p in root.iter() for c in p}
        def move(e, parent, i=None):
            parents[e].remove(e)
            if i is None:
                parent.append(e)
            else:
                parent.insert(i, e)
            parents[e] = e.parent = parent
        def split(e, after):
            """ Moves e (or what follows e if after) and later siblings into a copy
                of e's parent inserted after it. Returns the copy. """
            p = parents[e]
            res = p.copy(children=False)
            res.text, res.tail, p.tail = None, p.tail, None
            if after:
                res.text, e.tail = e.tail, None
            kids = list(p)
            for c in kids[kids.index(e) + (1 if after else 0):]:
                move(c, res)
            pp = parents[p]
            pp.insert(list(pp).index(p) + 1, res)
            parents[res] = res.parent = pp
            return res
        sancs = [start]
        while sancs[-1] in parents:
            sancs.append(parents[sancs[-1]])
        top = end
        while top not in sancs:
            top = parents[top]
        # top is the common ancestor. Split the end side so that what follows end
        # is in a separate element, and the start side so that start leads its
        # own element, at each level below top.
        endtext = None
        etop = end
        after = None
        while parents[etop] is not top:
            after = split(etop, True)
            etop = parents[etop]
        if after is None:
            endtext, end.tail = end.tail, None
        stop = start
        while parents[stop] is not top:
            stop = split(stop, False)
        head = None
        if stop is not start:
            head = top[list(top).index(stop) - 1]
            for c in list(stop)[1:]:
                move(c, start)
        start.text, start.tail = start.tail, None
        kids = list(top)
        body = kids[kids.index(stop)+1:kids.index(etop)+1]
        for c in body:
            move(c, start)
        parents[end].remove(end)
        if stop is not start:
            top.remove(stop)
            move(start, head)
        # what followed end continues the element holding start
        if after is not None and head is not None:
            start.tail = after.text
            for c in list(after):
                move(c, head)
            head.tail = after.tail
            top.remove(after)
        else:
            start.tail = endtext

    def _walk(self, e):
        """ Expands e and its contents in document order. Module milestones are
            executed and removed. """
        for k, v in e.attrib.items():
            e.set(k, self.expand(v, e))
        self._walkcontent(e)

    def _walkcontent(self, e):
        if e.text:
            e.text = self.expand(e.text, e)
        for c in list(e):
            fn = self.milestones.get(c.get("style", None), None) if c.tag == "ms" else None
            if fn is None:
                self._walk(c)
                rep = None
            else:
                try:
                    rep = fn(c) or ""
                except ModuleError as err:
                    self.errors.append((str(err), getattr(c, "pos", None)))
                    rep = self.errorfmt.format(err)
            if c.tail:
                c.tail = self.expand(c.tail, c)
            if rep is not None:
                self._replace(e, c, rep)

    @staticmethod
    def _replace(parent, e, s):
        """ Replaces element e with the text s """
        s += e.tail or ""
        i = list(parent).index(e)
        if i > 0:
            prev = parent[i-1]
            prev.tail = (prev.tail or "") + s
        else:
            parent.text = (parent.text or "") + s
        parent.remove(e)

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

    def evaluate(self, s: str) -> str:
        """ Expands a string, raising ModuleError on any failure, so that a failed
            value is never used """
        res = []
        for n in self._parse(s, 0, "")[0]:
            if n.iserror():
                raise ModuleError(n.s)
            res.append(self._eval(n))
        return "".join(res)

    def _eval(self, n) -> str:
        if n.isliteral():
            return n.s
        if n.isvar():
            if self._findvar(n.s) is None:
                return n.src                # not a variable, so literal
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
            elif nxt == "{" and (m := self._namere.match(s, i+2)) and s[m.end():m.end()+1] == "}":
                flush()
                nodes.append(Result(m.group(0), Result.VAR, s[i:m.end()+1]))
                i = m.end() + 1
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
                    nodes.append(Result(m.group(0), Result.VAR, s[i:m.end()]))
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

    def _runblock(self, e, bindings: Optional[Dict[str, Union[str, Dict[str, str]]]] = None,
                  chain: bool = True):
        """ Returns an expanded copy of the contents of block e, leaving e unchanged.
            Blocks run in the current frame. Given bindings (a macro call), the
            expansion runs in a new frame holding them, chained to the current
            frames, or if not chain, only to global. """
        res = e.copy(deep=True)
        res.tail = None
        saved = self.frames
        if bindings is not None:
            frame = {k: dict(v) if isinstance(v, dict) else {"*": v} for k, v in bindings.items()}
            self.frames = (saved if chain else saved[:1]) + [frame]
        try:
            self._walkcontent(res)
        finally:
            self.frames = saved
        return res

    def _usfm(self, e) -> str:
        """ Returns the contents of e as USFM text """
        root = e.__class__("usx", {"version": "3.1"})
        # inline content before any block goes in an unmarked para, which ends the line
        lead = e.__class__("para", {"style": ""})
        lead.text = e.text
        root.append(lead)
        for c in list(e):
            if len(root) > 1 or c.tag in ("para", "chapter", "row", "table", "sidebar"):
                root.append(c)
            else:
                lead.append(c)
        res = io.StringIO()
        usx2usfm(res, root, grammar=getattr(self.doc, "grammar", None))
        return res.getvalue()

    def setvar(self, name: str, value: str, lang: str = "*"):
        """ Writes a variable. If the name is bound in a non-global frame, the write
            goes to the innermost frame, else to global. """
        if any(name in f for f in self.frames[1:]):
            frame = self.frames[-1]
        else:
            frame = self.frames[0]
        frame.setdefault(name, {})[lang] = value

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

    @modulefn("get")
    def fn_get(self, name, lang=None, default=None):
        """ $get(name, [lang], [default]): reads a variable """
        return self.getvar(name, lang or "*", default)

    @modulems("mlet")
    def ms_mlet(self, e):
        """ \\mlet|var="name" val="value" [lang="tag"]\\*: assignment """
        name = self.evaluate(e.get("var", "")).strip()
        if not name:
            raise ModuleError("\\mlet has no var")
        lang = self.evaluate(e.get("lang", "")).strip() or "*"
        self.setvar(name, self.evaluate(e.get("val", "")), lang)

    @modulems("mlet-s", end="mlet-e")
    def ms_mlet_s(self, e):
        """ \\mlet-s|var="name" [lang="tag"]\\*..\\mlet-e\\*: assigns the expanded
            contents of the block, as USFM text """
        name = self.evaluate(e.get("var", "")).strip()
        if not name:
            raise ModuleError("\\mlet-s has no var")
        lang = self.evaluate(e.get("lang", "")).strip() or "*"
        self.setvar(name, self._usfm(self._runblock(e)).strip(), lang)


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
