""" Paratext module flattener.

A module is a USFM document containing \\m... milestones and $ expressions.
The Module class walks a parsed module document and expands its contents
into plain USFM/USX. Read modules with readModule or parseModule, which keep
the backslashes in quoted arguments and $# comments from the USFM parser.
"""

import re, inspect, io
from typing import Optional, Dict, List, Union
from usfmtc.reference import RefList, Environment
from usfmtc.usfmgenerate import usx2usfm


class ModuleError(Exception):
    """ A failure in one expansion. As it passes out through the evaluation it
        gathers context, innermost first, and the module line it happened on. """
    def __init__(self, msg: str):
        super().__init__(msg)
        self.context = []
        self.line = None

    def where(self, context: Optional[str] = None, line: Optional[int] = None):
        """ Adds context, and the line if not yet known. Returns self to raise. """
        if context:
            self.context.append(context)
        if self.line is None:
            self.line = line
        return self


class ModuleFatalError(Exception):
    """ A failure that ends the run, such as macro calls nested too deeply """
    pass


class Result:
    """ A node in a parsed expression: literal text, a quoted literal or a parse error """
    TEXT, QUOTED, ERROR, CALL, VAR = range(5)

    def __init__(self, s: str, kind: int = TEXT, src: Optional[str] = None, at: Optional[int] = None):
        self.s = s
        self.kind = kind
        self.src = src          # source text, where it differs from s
        self.at = at            # offset of the source in the expanded string
        self.namenodes = None   # for ${...}, the nodes giving the name

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
    def __init__(self, name: str, args: List[List[Result]], start: int, end: int, src: str):
        super().__init__(name, self.CALL, src, start)
        self.name = name
        self.args = args
        self.start = start
        self.end = end

    def __repr__(self):
        return f"Call({self.name}, {self.args!r})"


def modulefn(name: str, lazy: bool = False):
    """ Registers a method as the implementation of the module function $name.
        A lazy function is passed its arguments as functions that evaluate them. """
    def deco(fn):
        fn._modulefn = name
        fn._modulelazy = lazy
        return fn
    return deco


def modulems(name: str, end: Optional[str] = None, middle: Optional[str] = None):
    """ Registers a method as the handler of the module milestone \\name. It is
        passed the milestone element, whose attributes are not yet expanded. If
        end is given, \\name..\\end is a block and the element holds its contents.
        A middle milestone in the block is gathered as a block to the end. """
    def deco(fn):
        fn._modulems = name
        fn._modulemsend = end
        fn._modulemsmiddle = middle
        return fn
    return deco


_callre = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^}\n]*\})\(")

def protect(src: str) -> str:
    """ Doubles the backslashes in quoted arguments of $ calls and in $# comments
        of module source, so that the USFM parser, which reads \\\\ as \\, gives
        them back as written rather than as markers. A quote starts a literal
        only at the start of an argument, as in Module._parse. Any $name( is
        taken as a call, since macros are not known yet. """
    res = []
    i = 0
    depth = 0           # open parentheses in calls
    argstart = False    # at the start of an argument
    while i < len(src):
        c = src[i]
        if depth and argstart and c in "\"'":
            j = src.find(c, i + 1)
            if j < 0:                       # unterminated: _parse reports it
                res.append(src[i:])
                break
            res.append(c + src[i+1:j].replace("\\", "\\\\") + c)
            i = j + 1
            argstart = False
        elif src.startswith("$$", i):
            res.append("$$")
            i += 2
        elif src.startswith("$#", i):
            j = src.find("\n", i)
            j = len(src) if j < 0 else j
            res.append(src[i:j].replace("\\", "\\\\"))
            i = j
        elif c == "$" and (m := _callre.match(src, i)):
            res.append(m.group(0))
            i = m.end()
            depth += 1
            argstart = True
        else:
            res.append(c)
            i += 1
            if depth:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                argstart = (c == ",") or (argstart and c.isspace())
    return "".join(res)


def parseModule(text: str, extfiles: Optional[List[str]] = None, **kw):
    """ Parses module source text, returning a USX document """
    from usfmtc import readFile
    return readFile(protect(text), informat="usfm", extfiles=extfiles, **kw)


def readModule(fname: str, extfiles: Optional[List[str]] = None, **kw):
    """ Reads a module file, returning a USX document. As for readFile, a
        markers.ext beside the file is included. """
    import os
    with open(fname, encoding="utf-8-sig") as inf:
        text = inf.read()
    extfiles = list(extfiles or []) + [os.path.join(os.path.dirname(fname), "markers.ext")]
    return parseModule(text, extfiles=extfiles, **kw)


class Module:
    """ Flattens a parsed module document.

        doc is a USX object as read by usfmtc. envs maps language tags to reference
        Environments (e.g. BookNamesEnvironment) used to localise references;
        the "*" entry is the fallback. lang is the default language. variables
        gives initial global variables: name -> value, where a value is a string
        (its "*" form) or a dict of language tag -> string.

        Errors are collected in errors as (message, module line or None), where
        the message ends with where the error happened, innermost first. """

    errorfmt = "[ERROR: {}]"
    _protect = "\ufdd0"       # stands for a backslash of plain text while output is parsed
    listsep = "\x1c"
    pairsep = "\x1e"       # between key and value in a dict item
    _blocktags = ("book", "para", "chapter", "table", "row", "sidebar")
    _holdertags = ("usx", "ms", "sidebar")     # elements whose children are blocks
    _namere = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    maxdepth = 50               # macro call nesting limit

    def __init__(self, doc, envs: Optional[Dict[str, Environment]] = None, lang: Optional[str] = None,
                 variables: Optional[Dict[str, Union[str, Dict[str, str]]]] = None,
                 project=None, projects=None):
        """ project is the Project (see ptsettings) the module is flattened in: it gives
            the default language and its book names, and the scripture for references
            without a product. projects (a Projects) finds the projects of products. """
        self.doc = doc
        self.envs = dict(envs or {})
        self.project = project
        self.projects = projects
        if project is not None:
            self.lang = lang or project.lang
            self.envs.setdefault(project.lang, project.refenv)
            self.envs.setdefault("*", Environment())
        else:
            self.lang = lang or "*"
        self.frames = [{}]          # variable frames, global first: name -> {lang: value}
        for k, v in (variables or {}).items():
            self.frames[0][k] = dict(v) if isinstance(v, dict) else {"*": v}
        if self.lang != "*":
            self.frames[0].setdefault("LANG", {"*": self.lang})
        self.errors = []
        self.functions = {}
        self.milestones = {}
        self.blocks = {}            # start milestone -> end milestone
        self.middles = {}           # start milestone -> middle milestone
        self.macros = {}            # name -> (params, rest param or None, body)
        self.topdefs = set()        # top level \\mdef-s elements, removed by the walk
        self.depth = 0
        self.active = []            # what is running (macro calls, loops), outermost first
        self.locs = []              # (Pos, string) being expanded, innermost last
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
                if v._modulemsmiddle is not None:
                    self.middles[v._modulems] = v._modulemsmiddle

    def flatten(self):
        """ Returns a copy of the document with its contents expanded """
        res = self.doc.copy(deep=True)
        self._gather(res.getroot())
        self._macros(res.getroot())
        self._walk(res.getroot())
        return res

    def _gather(self, root):
        """ Turns each block milestone pair into a single start milestone element
            holding the block's contents. Inner blocks are gathered first. """
        ends = set(self.blocks.values())
        middles = set(self.middles.values())
        stack = []          # [start, middle or None]
        pairs = []
        for e in root.iter("ms"):
            s = e.get("style", None)
            if s in self.blocks:
                stack.append([e, None])
            elif s in ends:
                if stack and self.blocks[stack[-1][0].get("style")] == s:
                    pairs.append((*stack.pop(), e))
                else:
                    self._report(ModuleError(f"Unexpected \\{s}"), self._lineof(e))
            elif s in middles:
                if stack and stack[-1][1] is None and self.middles.get(stack[-1][0].get("style")) == s:
                    stack[-1][1] = e
                else:
                    self._report(ModuleError(f"Unexpected \\{s}"), self._lineof(e))
        for e, m in stack:
            self._report(ModuleError(f"Missing \\{self.blocks[e.get('style')]}"), self._lineof(e))
        for s, m, e in pairs:
            self._gatherblock(root, s, e)
            if m is not None:       # the middle holds the rest of the block
                last = e.__class__("ms", {}, parent=s)
                s.append(last)
                self._gatherblock(s, m, last)

    def _macros(self, root):
        """ Enters each top level \\mdef-s block of the gathered document into the
            macro table. The walk removes them and reports those inside blocks. """
        parents = {c: p for p in root.iter() for c in p}
        for e in list(root.iter("ms")):
            if e.get("style", None) != "mdef-s":
                continue
            p = parents[e]
            a = p
            while a.tag != "ms" and a in parents:
                a = parents[a]
            if a.tag == "ms":
                continue
            self.topdefs.add(e)
            try:
                self._defmacro(e)
            except ModuleError as err:
                self._report(err.where("in \\mdef-s", self._lineof(e)))

    def _defmacro(self, e):
        name = self._attr(e, "name").strip()
        if not self._namere.fullmatch(name):
            raise ModuleError(f"Bad macro name {name!r}")
        if name in self.macros or name in self.functions:
            raise ModuleError(f"${name} is already defined")
        params = [a.strip() for a in self._attr(e, "args").split(",")]
        params = [a for a in params if a]
        rest = None
        if params and params[-1].endswith(("…", "...")):
            rest = params.pop().rstrip(".…").strip()
        for a in params + ([rest] if rest is not None else []):
            if not self._namere.fullmatch(a):
                raise ModuleError(f"Bad parameter name {a!r} in ${name}")
        self.macros[name] = (params, rest, e)

    def _callmacro(self, name: str, args: List[str], line: Optional[int] = None) -> str:
        """ Runs a macro in a new frame holding its parameters, chained to global,
            returning its expanded contents as USFM text """
        params, rest, body = self.macros[name]
        if len(args) < len(params) or (rest is None and len(args) > len(params)):
            raise ModuleError(f"Wrong number of arguments ({len(args)}) to ${name}")
        bindings = dict(zip(params, args))
        if rest is not None:
            bindings[rest] = self._list(args[len(params):])
        if self.depth >= self.maxdepth:
            raise ModuleFatalError(f"Macro calls nested more than {self.maxdepth} deep in ${name}")
        self.depth += 1
        self.active.append(f"in macro ${name}" + (f" called at line {line}" if line else ""))
        try:
            return self._usfm(self._runblock(body, bindings, chain=False)).strip()
        finally:
            self.depth -= 1
            self.active.pop()

    @staticmethod
    def _gatherblock(root, start, end):
        """ Moves everything between start and end into start, removing end. Elements
            the block cuts across are split, and the part following end joins the
            element holding start, as if the block's text were not there. """
        parents = {c: p for p in root.iter() for c in p}
        def pos(e, which):
            return getattr(e, which + "pos", None)
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
            res.tailpos = pos(p, "tail")
            if after:
                res.text, e.tail = e.tail, None
                res.textpos = pos(e, "tail")
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
        endtext = endpos = None
        etop = end
        after = None
        while parents[etop] is not top:
            after = split(etop, True)
            etop = parents[etop]
        if after is None:
            endtext, end.tail = end.tail, None
            endpos = pos(end, "tail")
        stop = start
        while parents[stop] is not top:
            stop = split(stop, False)
        head = None
        if stop is not start:
            head = top[list(top).index(stop) - 1]
            for c in list(stop)[1:]:
                move(c, start)
        start.text, start.tail = start.tail, None
        start.textpos = pos(start, "tail")
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
            start.tail, start.tailpos = after.text, pos(after, "text")
            for c in list(after):
                move(c, head)
            head.tail, head.tailpos = after.tail, pos(after, "tail")
            top.remove(after)
        else:
            start.tail, start.tailpos = endtext, endpos

    def _walk(self, e):
        """ Expands e and its contents in document order. Module milestones are
            executed and removed. """
        for k, v in e.attrib.items():
            pos = getattr(e, "pos", None) or getattr(e, "textpos", None)  # attributes are on one line
            e.set(k, self.expand(v, pos, f"in {k} of \\{e.get('style', e.tag)}"))
        self._walkcontent(e)

    def _walkcontent(self, e):
        kids = list(e)      # what output adds is final, so is not walked
        if e.text:
            text, frag = self._output(e.text, getattr(e, "textpos", None) or getattr(e, "pos", None))
            e.text = text if frag is None else None
            if frag is not None:
                e = self._place(e, None, text, frag)
        for c in kids:
            fn = self.milestones.get(c.get("style", None), None) if c.tag == "ms" else None
            if fn is None:
                self._walk(c)
                rep = None
            else:
                try:
                    rep = fn(c) or ""
                except ModuleError as err:
                    rep = self._report(err.where(f"in \\{c.get('style')}", self._lineof(c)))
            frag = None
            if c.tail:
                text, frag = self._output(c.tail, getattr(c, "tailpos", None))
                c.tail = text if frag is None else None
                if frag is not None:    # a placeholder keeps the tail's place
                    ph = c.__class__("ms", {}, parent=e)
                    e.insert(list(e).index(c) + 1, ph)
            if isinstance(rep, list):
                e = self._splice(e, c, rep)     # later siblings may have moved
            elif rep is not None:
                self._replace(e, c, rep)
            if frag is not None:
                e = self._place(e, ph, text, frag)

    def _output(self, s: str, pos):
        """ Expands content text. Returns the text and, if values in it hold USFM
            markup, the text parsed as a fragment (see _fragment), else None. """
        parts = self._expandparts(s, pos)
        text = "".join(t for t, v in parts)
        if not any(v and "\\" in t for t, v in parts):
            return text, None
        try:
            return text, self._fragment(parts)
        except ModuleError as err:
            self._report(err, self._line())
            return text, None

    def _place(self, parent, ph, text, frag):
        """ Puts the parsed text frag in parent in place of the placeholder ph, or
            as its text if ph is None. Returns the element now holding what
            followed. If the markup can't go there, the text goes in as is. """
        if ph is None:
            ph = frag.__class__("ms", {}, parent=parent)
            parent.insert(0, ph)
        try:
            return self._splice(parent, ph, [frag])
        except ModuleError as err:
            self._report(err.where("in output text"), self._lineof(parent))
            self._replace(parent, ph, text)
            return parent

    def _fragment(self, parts):
        """ Parses the (text, is value) parts as USFM. Only values are markup.
            Returns an element holding the leading inline content then any blocks. """
        from usfmtc import readFile
        s = "".join(t if v else t.replace("\\", self._protect) for t, v in parts)
        try:
            doc = readFile("\\id GEN\n\\p " + s, informat="usfm",
                           grammar=getattr(self.doc, "grammar", None))
        except Exception as err:
            raise ModuleError(f"Can't parse output {self._brief(s)!r}: {err}")
        if doc is None:
            raise ModuleError(f"Can't parse output {self._brief(s)!r}")
        root = doc.getroot()
        kids = [c for c in root if c.tag != "book"]
        res = root.__class__("usx", {})
        lead = kids.pop(0)
        res.text = lead.text
        for c in list(lead) + kids:
            res.append(c)
            c.parent = res
        for e in res.iter():
            for k, v in e.attrib.items():
                e.set(k, v.replace(self._protect, "\\"))
            if e.text:
                e.text = e.text.replace(self._protect, "\\")
            if e.tail:
                e.tail = e.tail.replace(self._protect, "\\")
        # whitespace at the ends belongs to the context, whatever the parser kept
        lws = s[:len(s) - len(s.lstrip())]
        tws = s[len(s.rstrip()):]
        res.text = lws + (res.text or "").lstrip()
        last = res[-1] if len(res) and res[-1].tag in self._blocktags else res
        if last.tag in ("usx", "para"):
            if len(last):
                last[-1].tail = (last[-1].tail or "").rstrip() + tws
            else:
                last.text = (last.text or "").rstrip() + tws
        return res

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

    @classmethod
    def _splice(cls, parent, e, containers):
        """ Replaces block element e in parent with the contents of the expanded
            containers, as if their USFM text stood in place of e: inline content
            continues the current paragraph and block level content starts a new
            one. Unless parent holds blocks, the blocks become its siblings and what
            followed e continues the last of them. Returns the element now holding
            what followed e. """
        class Cursor:
            """ An insertion point: the end of what precedes index i in el """
            def __init__(self, el, i):
                self.el, self.i = el, i
            def text(self, s):
                if not s:
                    return
                if self.i > 0:
                    prev = self.el[self.i-1]
                    prev.tail = (prev.tail or "") + s
                else:
                    self.el.text = (self.el.text or "") + s
            def add(self, c):
                self.el.insert(self.i, c)
                c.parent = self.el
                self.i += 1
        hasblocks = any(c.tag in cls._blocktags for b in containers for c in b)
        split = hasblocks and parent.tag not in cls._holdertags
        if split and (parent.tag not in cls._blocktags or parent.parent is None):
            raise ModuleError(f"No room for paragraphs in \\{parent.get('style', parent.tag)}")
        i = list(parent).index(e)
        parent.remove(e)
        if not split:
            following = None
            inline = blocks = Cursor(parent, i)
        else:
            following = list(parent)[i:]
            for c in following:
                parent.remove(c)
            inline = Cursor(parent, i)
            pp = parent.parent
            blocks = Cursor(pp, list(pp).index(parent) + 1)
        for b in containers:
            inline.text(b.text)
            for c in list(b):
                b.remove(c)
                tail, c.tail = c.tail, None
                if c.tag in cls._blocktags:
                    blocks.add(c)
                    inline = Cursor(c, len(c))
                else:
                    inline.add(c)
                inline.text(tail)
        inline.text(e.tail)
        if following is None:
            return parent
        for c in following:
            inline.add(c)
        return inline.el

    def expand(self, s: str, pos=None, where: Optional[str] = None) -> str:
        """ Expands a content string, which starts at pos in the module. Each top
            level expansion that fails is replaced by an error marker and the error
            recorded, with where as its outermost context. """
        return "".join(t for t, v in self._expandparts(s, pos, where))

    def _expandparts(self, s: str, pos=None, where: Optional[str] = None):
        """ Expands as for expand, returning (text, is a value) parts """
        res = []
        self.locs.append((pos, s))
        try:
            for n in self._parse(s, 0, "")[0]:
                if n.isliteral():
                    res.append((n.s, False))
                    continue
                try:
                    if n.iserror():
                        raise ModuleError(n.s)
                    v = self._eval(n)
                    if self.listsep in v or self.pairsep in v:
                        raise ModuleError("A list can't be output, use $join()").where(
                            f"in {self._brief(n.src)}")
                    res.append((v, True))
                except ModuleError as err:
                    res.append((self._report(err.where(where, self._line(n.at))), False))
        finally:
            self.locs.pop()
        return res

    def evaluate(self, s: str, pos=None) -> str:
        """ Expands a string, which starts at pos in the module, raising ModuleError
            on any failure, so that a failed value is never used """
        res = []
        self.locs.append((pos, s))
        try:
            for n in self._parse(s, 0, "")[0]:
                if n.iserror():
                    raise ModuleError(n.s).where(line=self._line(n.at))
                res.append(self._eval(n))
        finally:
            self.locs.pop()
        return "".join(res)

    def _attr(self, e, name: str) -> str:
        """ Evaluates attribute name of the milestone e """
        v = e.get(name, "")
        try:
            return self.evaluate(v, getattr(e, "pos", None))
        except ModuleError as err:
            raise err.where(f'in {name}="{self._brief(v)}"')

    def _report(self, err: ModuleError, line: Optional[int] = None) -> str:
        """ Records an error with its context and what is running, returning the
            error marker for the output """
        err.where(line=line)
        self.errors.append(("; ".join([str(err)] + err.context + self.active[::-1]), err.line))
        return self.errorfmt.format(err)

    def _line(self, at: Optional[int] = None) -> Optional[int]:
        """ The module line of offset at in the string being expanded """
        if not self.locs or self.locs[-1][0] is None:
            return None
        pos, s = self.locs[-1]
        return pos.l + 1 + (s.count("\n", 0, at) if at else 0)

    @staticmethod
    def _lineof(e) -> Optional[int]:
        pos = getattr(e, "pos", None)
        return pos.l + 1 if pos is not None else None

    @staticmethod
    def _brief(s: str, n: int = 40) -> str:
        """ s in brief, for error messages """
        s = " ".join(s.split())
        return s if len(s) <= n else s[:n-1] + "…"

    def _eval(self, n) -> str:
        if n.isliteral():
            return n.s
        if n.isvar():
            if n.namenodes is not None:
                try:
                    return self.getvar(self._name(n.namenodes))
                except ModuleError as err:
                    raise err.where(f"in {self._brief(n.src)}", self._line(n.at))
            if self._findvar(n.s) is None:
                return n.src                # not a variable, so literal
            return self.getvar(n.s)
        name = n.name
        try:
            if n.namenodes is not None:
                name = self._name(n.namenodes)
                if name not in self.functions and name not in self.macros:
                    raise ModuleError(f"No function or macro ${name}")
            fn = self.functions.get(name, None)
            if getattr(fn, "_modulelazy", False):
                args = [lambda a=a: "".join(self._eval(x) for x in a) for a in n.args]
            else:
                args = ["".join(self._eval(x) for x in a) for a in n.args]
            if name in self.macros:
                return self._callmacro(name, args, self._line(n.at))
            try:
                inspect.signature(fn).bind(*args)
            except TypeError:
                raise ModuleError(f"Wrong number of arguments ({len(args)}) to ${name}")
            return fn(*args)
        except ModuleError as err:
            # the innermost call is shown in full, the calls around it by name
            raise err.where(f"in ${name}" if err.context else f"in {self._brief(n.src)}",
                            self._line(n.at))

    def _name(self, nodes) -> str:
        """ Evaluates the contents of ${...} as a name """
        name = "".join(self._eval(x) for x in nodes).strip()
        if not self._namere.fullmatch(name):
            raise ModuleError(f"Bad name {name!r}")
        return name

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
                nodes.append(Result(m.group(0), Result.VAR, s[i:m.end()+1], i))
                i = m.end() + 1
            elif nxt == "{":                    # ${...} computes a name
                try:
                    inner, j = self._parse(s, i+2, "}")
                    if j >= len(s):             # no }, so literal
                        text.append("$")
                        i += 1
                        continue
                    flush()
                    if s[j+1:j+2] == "(":
                        node, j = self._parsecall(s, s[i+1:j+1], i, j+2)
                    else:
                        node, j = Result(s[i:j+1], Result.VAR, s[i:j+1], i), j+1
                    node.namenodes = inner
                except ModuleError as err:
                    if stops:
                        raise
                    flush()
                    node, j = Result(str(err), Result.ERROR, at=i), len(s)
                nodes.append(node)
                i = j
            elif nxt == "#":
                j = s.find("\n", i)
                i = len(s) if j < 0 else j
            elif (m := self._namere.match(s, i+1)):
                flush()
                if (m.group(0) in self.functions or m.group(0) in self.macros) \
                        and s[m.end():m.end()+1] == "(":
                    try:
                        call, i = self._parsecall(s, m.group(0), i, m.end() + 1)
                    except ModuleError as err:
                        if stops:
                            raise
                        call, i = Result(str(err), Result.ERROR, at=i), len(s)   # a top level syntax error consumes the rest
                    nodes.append(call)
                else:
                    nodes.append(Result(m.group(0), Result.VAR, s[i:m.end()], i))
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
            return _Call(name, args, start, m.end(), s[start:m.end()]), m.end()
        while True:
            arg, i = self._parse(s, i, ",)")
            args.append(self._stripws(arg))
            if i >= len(s):
                raise ModuleError(f"Missing ) in call to ${name}")
            i += 1
            if s[i-1] == ")":
                return _Call(name, args, start, i, s[start:i]), i

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
            if len(root) > 1 or c.tag in self._blocktags:
                root.append(c)
            else:
                lead.append(c)
        res = io.StringIO()
        usx2usfm(res, root, grammar=getattr(self.doc, "grammar", None))
        return re.sub(r"\s*\n\s*", "\n", res.getvalue())    # line breaks are just spaces

    def setvar(self, name: str, value: str, lang: str = "*"):
        """ Writes a variable. If the name is bound in a non-global frame, the write
            goes to the innermost frame, else to global. """
        if any(name in f for f in self.frames[1:]):
            frame = self.frames[-1]
        else:
            frame = self.frames[0]
        frame.setdefault(name, {})[lang] = value

    def _env(self, lang: Optional[str]) -> Environment:
        """ The reference environment for lang, else $LANG, else the module's
            language, falling back to the "*" environment """
        lang = (lang or "").strip() or self.getvar("LANG", "*", "").strip() or self.lang
        env = self.envs.get(lang, self.envs.get("*", None))
        if env is None:
            raise ModuleError(f"No reference environment for language {lang}")
        return env

    def _project(self, product: Optional[str]):
        """ The project to take a reference's scripture from: the module's project,
            or the one for the reference's product, e.g. en+BSB """
        if not product:
            if self.project is None:
                raise ModuleError("No project to take scripture from")
            return self.project
        res = self.projects.find(product) if self.projects is not None else None
        if res is None:
            raise ModuleError(f"No project for {product}")
        return res

    def _refs(self, ref: str, env: Environment) -> RefList:
        """ Parses a reference list, which may use the local book names of env """
        try:
            refs = RefList(ref, env=env)
        except (SyntaxError, ValueError) as err:
            raise ModuleError(f"Bad reference {ref!r}: {err}")
        if not len(refs):
            raise ModuleError("Empty reference")
        return refs

    def _localref(self, ref: str, level: int, lang: Optional[str]) -> str:
        env = self._env(lang)
        return self._refs(ref, env).str(env=env, level=level)

    @modulefn("a")
    def fn_a(self, ref, lang=None):
        """ $a(ref, [lang]): abbreviated localised form of a reference """
        return self._localref(ref, 0, lang)

    @modulefn("s")
    def fn_s(self, ref, lang=None):
        """ $s(ref, [lang]): short localised form of a reference """
        return self._localref(ref, 1, lang)

    @modulefn("l")
    def fn_l(self, ref, lang=None):
        """ $l(ref, [lang]): long localised form of a reference """
        return self._localref(ref, 2, lang)

    @modulefn("r")
    def fn_r(self, ref, path=None, lang=None):
        """ $r(ref, [path], [lang]): the canonical form of a reference list, which
            may use local book names, or the part of it that path selects """
        refs = self._refs(ref, self._env(lang))
        return self._refpath(refs, path or "")

    _refparts = ("book", "chapter", "verse")

    def _refpath(self, refs: RefList, path: str) -> str:
        """ Follows a $r path of dot separated parts. On the list, a number (from
            0, negative from the end), first or last chooses a range; on a range,
            first or last chooses its start or end reference; book, chapter or
            verse gives that part of a reference, of the end of a range or list. """
        cur, depth = refs, 0        # depth: 0 list, 1 range, 2 reference, 3 part
        for p in (x.strip() for x in path.split(".")):
            if not p:
                continue
            if depth == 3:
                raise ModuleError(f"Nothing can follow a part in $r path {path!r}")
            if p in self._refparts:
                if depth == 0:
                    cur = cur[-1]
                if depth <= 1:
                    cur = cur.last.end()
                v = getattr(cur, p, None)
                if p == "verse" and v is not None and cur.subverse:
                    v = f"{v}{cur.subverse}"
                cur, depth = ("" if v is None else str(v)), 3
            elif p in ("first", "last"):
                if depth == 0:
                    cur = cur[0 if p == "first" else -1]
                elif depth == 1:
                    cur = cur.first.start() if p == "first" else cur.last.end()
                depth = min(depth + 1, 2)
            elif depth == 0 and re.fullmatch(r"[+-]?\d+", p):
                i = int(p)
                if not -len(cur) <= i < len(cur):
                    raise ModuleError(f"No range {i} in {cur.str()}")
                cur, depth = cur[i], 1
            else:
                raise ModuleError(f"Bad part {p!r} in $r path {path!r}")
        return cur if depth == 3 else cur.str()

    @modulefn("sub")
    def fn_sub(self, s, regex, repl):
        """ $sub(string, regex, replacement): as Python's re.sub. A backslash is
            written \\\\ in USFM. """
        try:
            return re.sub(regex, repl, s)
        except re.error as err:
            raise ModuleError(f"Bad regex or replacement in $sub: {err}")

    @modulefn("match")
    def fn_match(self, s, regex):
        """ $match(string, regex): searches string, as Python's re.search. Without
            groups in regex, gives 1 or 0. With groups, gives the list of the whole
            match then each group, so item n is group n, or the empty list if there
            is no match. """
        try:
            r = re.compile(regex)
        except re.error as err:
            raise ModuleError(f"Bad regex in $match: {err}")
        m = r.search(s)
        if not r.groups:
            return "1" if m else "0"
        if m is None:
            return ""
        return self._list(g or "" for g in (m.group(0),) + m.groups())

    @modulefn("e")
    def fn_e(self, s):
        """ $e(string): expands string, such as the contents of a quoted literal """
        return self.evaluate(s)

    @modulefn("get")
    def fn_get(self, name, lang=None, default=None):
        """ $get(name, [lang], [default]): reads a variable """
        return self.getvar(name, lang or "*", default)

    def _items(self, s: str) -> List[str]:
        """ The items of a list. The empty string is the empty list. """
        return s.split(self.listsep) if s else []

    def _list(self, items) -> str:
        return self.listsep.join(items)

    def _isdict(self, items: List[str]) -> bool:
        return all(self.pairsep in i for i in items)

    @staticmethod
    def _int(s: str, fn: str) -> int:
        try:
            return int(s)
        except ValueError:
            raise ModuleError(f"${fn} needs a number, not {s!r}")

    @modulefn("list")
    def fn_list(self, *args):
        """ $list(item, ...): a list of the items, splicing in the items of lists """
        return self._list(i for a in args for i in self._items(a))

    @modulefn("split")
    def fn_split(self, s, delim=","):
        """ $split(string, [delimiter]): a list of the parts of string """
        if not delim:
            raise ModuleError("$split has an empty delimiter")
        return self._list(s.split(delim)) if s else ""

    @modulefn("join")
    def fn_join(self, joiner, *args):
        """ $join(joiner, item, ...): the items, and the items of lists, joined """
        return joiner.join(i for a in args for i in self._items(a))

    @modulefn("strip")
    def fn_strip(self, s):
        """ $strip(list): strips whitespace from each item """
        return self._list(i.strip() for i in self._items(s))

    @modulefn("len")
    def fn_len(self, s):
        """ $len(list): the number of items in a list or dict """
        return str(len(self._items(s)))

    @modulefn("range")
    def fn_range(self, *args):
        """ $range([first], last, [step]): a list of the numbers from first (0) up
            to but not including last """
        if not 1 <= len(args) <= 3:
            raise ModuleError(f"Wrong number of arguments ({len(args)}) to $range")
        vals = [self._int(a, "range") for a in args]
        if len(vals) == 3 and vals[2] == 0:
            raise ModuleError("$range step is 0")
        return self._list(str(i) for i in range(*vals))

    @modulefn("dict")
    def fn_dict(self, keys, values=None):
        """ $dict(list, [values]): a dict from a list of key, value, key, value...
            or from a list of keys and a list of values or a single value for all """
        keys = self._items(keys)
        if values is None:
            if len(keys) % 2:
                raise ModuleError("$dict needs a value for each key")
            keys, vals = keys[::2], keys[1::2]
        else:
            vals = self._items(values)
            if len(vals) == 1:
                vals = vals * len(keys)
            elif len(vals) != len(keys):
                raise ModuleError(f"$dict has {len(keys)} keys and {len(vals)} values")
        return self._list(k + self.pairsep + v for k, v in zip(keys, vals))

    @modulefn("iget")
    def fn_iget(self, value, index, default=None):
        """ $iget(list, index, [default]): the item at a 0 based index in a list, or
            with a key in a dict """
        items = self._items(value)
        if items and self._isdict(items):
            for i in items:
                k, v = i.split(self.pairsep, 1)
                if k == index:
                    return v
        else:
            i = self._int(index, "iget")
            if -len(items) <= i < len(items):
                return items[i]
        if default is None:
            raise ModuleError(f"No item {index!r}")
        return default

    _numre = re.compile(r"\s*[+-]?(\d+(\.\d*)?|\.\d+)\s*")
    _falses = ("", "0", "f", "false", "n", "no")

    def _num(self, s: str):
        """ The number s holds, or None """
        if not self._numre.fullmatch(s):
            return None
        return float(s) if "." in s else int(s)

    @staticmethod
    def _numstr(v) -> str:
        """ The shortest form of a number: 4/2 is 2 """
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v)

    @classmethod
    def _truth(cls, s: str) -> bool:
        """ Whether a condition is true: anything but empty, 0, f, false, n, no """
        return s.strip().lower() not in cls._falses

    def _natkey(self, s: str):
        """ Natural ordering: runs of digits compare as numbers """
        return [(0, int(r), "") if r.isdigit() else (1, 0, r) for r in re.split(r"(\d+)", s) if r]

    def _compare(self, a: str, b: str) -> int:
        na, nb = self._num(a), self._num(b)
        ka, kb = (na, nb) if na is not None and nb is not None else (self._natkey(a), self._natkey(b))
        return (ka > kb) - (ka < kb)

    @modulefn("op")
    def fn_op(self, op, *vals):
        """ $op(op, val, ...): applies op to the values. Arithmetic (+ - * / // %)
            reduces across them, comparisons (< > = !=) take two. """
        op = op.strip()
        comparisons = {"<": lambda c: c < 0, ">": lambda c: c > 0, "=": lambda c: c == 0,
                       "!=": lambda c: c != 0}
        if op in comparisons:
            if len(vals) != 2:
                raise ModuleError(f"$op({op}) compares 2 values, not {len(vals)}")
            return "1" if comparisons[op](self._compare(*vals)) else "0"
        arith = {"+", "-", "*", "/", "//", "%"}
        if op not in arith:
            raise ModuleError(f"Unknown operator {op!r}")
        if not vals:
            raise ModuleError(f"$op({op}) has no values")
        nums = [self._num(v) for v in vals]
        if op == "+" and any(self.listsep in v for v in vals):
            return self._list(i for v in vals for i in self._items(v))
        if op == "+" and None in nums:
            return "".join(vals)
        if op == "*" and nums[0] is None:
            if None in nums[1:] or any(isinstance(n, float) or n < 0 for n in nums[1:]):
                raise ModuleError(f"$op(*) repeats a string a whole number of times")
            count = 1
            for n in nums[1:]:
                count *= n
            if self.listsep in vals[0]:
                return self._list(self._items(vals[0]) * count)
            return vals[0] * count
        if None in nums:
            bad = vals[nums.index(None)]
            raise ModuleError(f"$op({op}) needs numbers, not {bad!r}")
        fns = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
               "/": lambda a, b: a / b, "//": lambda a, b: a // b, "%": lambda a, b: a % b}
        res = nums[0]
        for n in nums[1:]:
            try:
                res = fns[op](res, n)
            except ZeroDivisionError:
                raise ModuleError(f"$op({op}) divides by 0")
        return self._numstr(res)

    @modulefn("bool")
    def fn_bool(self, val):
        """ $bool(val): 0 if val is false (see _truth), else 1 """
        return "1" if self._truth(val) else "0"

    @modulefn("not")
    def fn_not(self, cond):
        """ $not(cond): 1 if cond is false, else 0 """
        return "0" if self._truth(cond) else "1"

    @modulefn("and", lazy=True)
    def fn_and(self, *conds):
        """ $and(cond, ...): 1 if all the conditions are true. Stops at the first false one. """
        return "1" if all(self._truth(c()) for c in conds) else "0"

    @modulefn("or", lazy=True)
    def fn_or(self, *conds):
        """ $or(cond, ...): 1 if any condition is true. Stops at the first true one. """
        return "1" if any(self._truth(c()) for c in conds) else "0"

    @modulefn("if", lazy=True)
    def fn_if(self, cond, then, otherwise=None):
        """ $if(cond, then, [else]): then if cond is true, else the else value. Only
            the value chosen is evaluated. """
        if self._truth(cond()):
            return then()
        return otherwise() if otherwise is not None else ""

    @modulefn("rall")
    def fn_rall(self, ref, level=None):
        """ $rall(ref, [level]): a list of the books (b), chapters (c) or verses (v)
            in a canonical ref list, or with no level its ranges. Partial books
            and chapters stay as ranges. """
        try:
            refs = RefList(ref)
        except SyntaxError as err:
            raise ModuleError(f"Bad reference {ref!r}: {err}")
        items = {None: lambda: refs, "": lambda: refs, "b": refs.allbooks,
                 "c": refs.allchaps, "v": refs.allrefs}.get(level, None)
        if items is None:
            raise ModuleError(f"Bad level {level!r} to $rall")
        return self.listsep.join(r.str() for r in items())

    @modulems("mlet")
    def ms_mlet(self, e):
        """ \\mlet|var="name" val="value" [lang="tag"]\\*: assignment """
        name = self._attr(e, "var").strip()
        if not name:
            raise ModuleError("\\mlet has no var")
        lang = self._attr(e, "lang").strip() or "*"
        self.setvar(name, self._attr(e, "val"), lang)

    @modulems("mlet-s", end="mlet-e")
    def ms_mlet_s(self, e):
        """ \\mlet-s|var="name" [lang="tag"]\\*..\\mlet-e\\*: assigns the expanded
            contents of the block, as USFM text """
        name = self._attr(e, "var").strip()
        if not name:
            raise ModuleError("\\mlet-s has no var")
        lang = self._attr(e, "lang").strip() or "*"
        self.setvar(name, self._usfm(self._runblock(e)).strip(), lang)

    @modulems("miset")
    def ms_miset(self, e):
        """ \\miset|var="name" index="i" val="value" [lang="tag"]\\*: sets item i of
            a list, or key i of a dict, adding it if it is missing """
        self._iset(e, self._attr(e, "val"))

    @modulems("miset-s", end="miset-e")
    def ms_miset_s(self, e):
        """ \\miset-s|var="name" index="i" [lang="tag"]\\*..\\miset-e\\*: sets the item
            to the expanded contents of the block, as USFM text """
        self._iset(e, self._usfm(self._runblock(e)).strip())

    def _iset(self, e, value: str):
        style = e.get("style")
        name = self._attr(e, "var").strip()
        if not name:
            raise ModuleError(f"\\{style} has no var")
        index = self._attr(e, "index").strip()
        lang = self._attr(e, "lang").strip() or "*"
        if self.listsep in value or self.pairsep in value:
            raise ModuleError(f"\\{style} can't set an item to a list")
        items = self._items(self.getvar(name, lang, ""))
        isnum = re.fullmatch(r"[+-]?\d+", index) is not None
        if self._isdict(items) and (items or not isnum):
            if self.listsep in index or self.pairsep in index:
                raise ModuleError(f"\\{style} can't use a list as a key")
            pair = index + self.pairsep + value
            for j, item in enumerate(items):
                if item.split(self.pairsep, 1)[0] == index:
                    items[j] = pair
                    break
            else:
                items.append(pair)
        else:
            if not isnum:
                raise ModuleError(f"A list index must be a number, not {index!r}")
            i = int(index)
            if i < 0:
                if i < -len(items):
                    raise ModuleError(f"No item {i} in a list of {len(items)}")
                i += len(items)
            items.extend([""] * (i + 1 - len(items)))     # a later index extends the list
            items[i] = value
        self.setvar(name, self._list(items), lang)

    @modulems("mdef-s", end="mdef-e")
    def ms_mdef_s(self, e):
        """ \\mdef-s|name="name" args="a, b, rest…"\\*..\\mdef-e\\*: defines the macro
            $name. Top level ones are entered before the walk and removed here. """
        if e not in self.topdefs:
            raise ModuleError("\\mdef-s must be at the top level")

    @modulems("mif-s", end="mif-e", middle="melse")
    def ms_mif_s(self, e):
        """ \\mif-s|cond="cond"\\*..[\\melse\\*..]\\mif-e\\*: expands the block if
            cond is true, else what follows \\melse """
        cond = self._truth(self._attr(e, "cond"))
        if cond:
            return [self._runblock(e)]      # which removes the \\melse part
        for m in self._blockiter(e):
            if m.tag == "ms" and m.get("style", None) == "melse":
                return [self._runblock(m)]
        return []

    @modulems("melse")
    def ms_melse(self, e):
        """ \\melse\\*: the else part of a true \\mif-s, which is dropped, or a
            stray one, already reported """
        return ""

    def _blockiter(self, e):
        """ Iterates the contents of block e, without going into the blocks in it """
        for c in e:
            yield c
            if not (c.tag == "ms" and c.get("style", None) in self.blocks):
                yield from self._blockiter(c)

    @modulems("mfor-s", end="mfor-e")
    def ms_mfor_s(self, e):
        """ \\mfor-s|var="name" list="list" [slice="slice"]\\*..\\mfor-e\\*: expands
            the block once for each item in list, with var bound to the item in the
            enclosing frame. A dict item is bound as a [key, value] list. """
        name = self._attr(e, "var").strip()
        if not name:
            raise ModuleError("\\mfor-s has no var")
        items = self._items(self._attr(e, "list"))
        items = self._slice(items, self._attr(e, "slice").strip())
        items = [i.replace(self.pairsep, self.listsep, 1) for i in items]
        frame = self.frames[-1]
        saved = frame.get(name, None)
        res = []
        try:
            for i, item in enumerate(items):
                frame[name] = {"*": item}
                self.active.append(f"in \\mfor-s at line {self._lineof(e)} with ${name}={self._brief(item)!r} (item {i})")
                try:
                    res.append(self._runblock(e))
                finally:
                    self.active.pop()
        finally:
            if saved is None:
                frame.pop(name, None)
            else:
                frame[name] = saved
        return res

    def _slice(self, items: List[str], spec: str) -> List[str]:
        """ Applies an \\mfor slice: keys or values of a dict, or a Python
            start:stop:step slice of any list """
        if not spec:
            return items
        if spec in ("keys", "values"):
            if not self._isdict(items):
                raise ModuleError(f"slice=\"{spec}\" of a list that is not a dict")
            return [i.split(self.pairsep, 1)[spec == "values"] for i in items]
        parts = spec.split(":")
        try:
            if not 2 <= len(parts) <= 3:
                raise ValueError
            return items[slice(*(int(p) if p.strip() else None for p in parts))]
        except ValueError:
            raise ModuleError(f"Bad slice {spec!r}")
