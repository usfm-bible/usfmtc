import pytest
from pytest import fail
from usfmtc.module import Module, ModuleError, ModuleFatalError, protect, flattenModuleFile
from usfmtc.usfm import readFile
from usfmtc.usfmmodule import main
from usfmtc.reference import BookNamesEnvironment
import os

def parseModule(text):
    return readFile(text, informat="usfm", preprocess=protect)

bkenv = BookNamesEnvironment(os.path.join(os.path.dirname(__file__), "BookNames.xml"))

variables = {"ref": "JDG 3:4", "name": "Fred", "title": {"*": "Lexicon", "es": "Léxico"},
             "es_only": {"es": "Hola"}}

def _mod(doc=None):
    return Module(doc, envs={"*": bkenv}, variables=variables)

def _e(s, res, errors=0):
    mod = _mod()
    out = mod.expand(s)
    if out != res:
        fail(f"{s!r} expanded to {out!r} instead of {res!r}")
    if len(mod.errors) != errors:
        fail(f"{s!r} gave {len(mod.errors)} errors instead of {errors}: {mod.errors}")

@pytest.mark.parametrize("s, res", [
    ("No expressions here", "No expressions here"),
    ("$s(JDG 3:4)", "Judges 3:4"),
    ("See $s(JHN 3:16) and $s(GEN 1:1)", "See John 3:16 and Genesis 1:1"),
    ("$s( JHN 3:16 )", "John 3:16"),
    ("$s(\"JHN 3:16\")", "John 3:16"),
    ("$s(JHN 3:16, en)", "John 3:16"),
    ("$s(PSA 23:1-3)", "Psalms 23:1-3"),
    ("Costs $$5", "Costs $5"),
    ("A${}B", "AB"),
    ("$unknown(x) stays", "$unknown(x) stays"),
    ("$s stays", "$s stays"),
])
def test_expand(s, res):
    _e(s, res)

@pytest.mark.parametrize("s, res", [
    ("$s(GEN 1:1, en, x)", "[ERROR: Wrong number of arguments (3) to $s]"),
    ("$s()", "[ERROR: Wrong number of arguments (0) to $s]"),
    ("$s(GEN 1:1", "[ERROR: Missing ) in call to $s]"),
    ("ok $s(GEN 1:1, a, b) then $s(JHN 1:1)", "ok [ERROR: Wrong number of arguments (3) to $s] then John 1:1"),
])
def test_errors(s, res):
    _e(s, res, errors=1)

@pytest.mark.parametrize("s, res", [
    ("Hello $name", "Hello Fred"),
    ("$name's book", "Fred's book"),
    ("$title", "Lexicon"),
    ("$s($ref)", "Judges 3:4"),
    ("$nobody stays", "$nobody stays"),
    ("$$name", "$name"),
    ("$name${}s", "Freds"),
    ("${name}s", "Freds"),
    ("${nobody}s", "${nobody}s"),
    ("${name", "${name"),
    ("$get(name)", "Fred"),
    ("$get( title , es )", "Léxico"),
    ("$get(title, fr)", "Lexicon"),
    ("$get(nobody, *, Anon)", "Anon"),
    ("$s($get(ref))", "Judges 3:4"),
])
def test_vars(s, res):
    _e(s, res)

def test_var_quoted():
    mod = _mod()
    out = mod.expand("$s('$ref')")
    if not out.startswith("[ERROR: Bad reference '$ref'") or len(mod.errors) != 1:
        fail(f"Quoted $ref was expanded: {out}")

def test_var_nostar():
    _e("$es_only", "[ERROR: No value for $es_only]", errors=1)

def test_getvar_lang():
    mod = _mod()
    for lang, res in (("es", "Léxico"), ("fr", "Lexicon"), ("*", "Lexicon")):
        if (v := mod.getvar("title", lang)) != res:
            fail(f"title in {lang} gave {v} instead of {res}")
    if mod.getvar("es_only", "fr", "none") != "none":
        fail("es_only in fr did not give the default")

def test_flatten():
    usfm = r"""\id GEN module test
\c 1
\p
\v 1 See $s(JDG 3:4) and $s(JHN 3:16).
"""
    doc = parseModule(usfm)
    res = _mod(doc).flatten().outUsfm(None)
    if "See Judges 3:4 and John 3:16." not in res:
        fail(f"Flattened to {res}")
    if "$s" not in doc.outUsfm(None):
        fail("Flattening changed the original document")

def test_get_errors():
    _e("$get(nobody)", "[ERROR: No value for $nobody]", errors=1)
    _e("$get(es_only, fr, '')", "", errors=0)
    _e("$get(es_only, fr)", "[ERROR: No value for $es_only in fr]", errors=1)

def _flatten(usfm, errors=0):
    mod = _mod(parseModule(usfm))
    res = mod.flatten().outUsfm(None)
    if len(mod.errors) != errors:
        fail(f"{len(mod.errors)} errors instead of {errors}: {mod.errors}")
    return res

def test_mlet():
    res = _flatten(r"""\id GEN module test
\mlet|var="who" val="Jane"\*
\c 1
\p
\v 1 $who read \mlet|var="where" val="$s($ref)"\*$where.
\v 2 \mlet|var="name" val="Joe" lang="es"\*$get(name, es) and $name.
""")
    for s in ("Jane read Judges 3:4.", "Joe and Fred."):
        if s not in res:
            fail(f"{s} not in {res}")
    if "mlet" in res:
        fail(f"mlet left in output {res}")

def test_mlet_order():
    """ A variable is only set from where the \\mlet is """
    res = _flatten(r"""\id GEN module test
\c 1
\p
\v 1 $later \mlet|var="later" val="now"\*$later
""")
    if "$later now" not in res:
        fail(f"Wrong order in {res}")

def test_mlet_error():
    res = _flatten(r"""\id GEN module test
\c 1
\p
\v 1 A\mlet|var="bad" val="$s(GEN 1:1, a, b)"\*B $bad
""", errors=1)
    if "A[ERROR: Wrong number of arguments (3) to $s]B $bad" not in res:
        fail(f"Failed \\mlet not reported in place: {res}")

def _vars(usfm, errors=0):
    """ Flattens usfm, returning the output and global variables """
    mod = _mod(parseModule(usfm))
    res = mod.flatten().outUsfm(None)
    if len(mod.errors) != errors:
        fail(f"{len(mod.errors)} errors instead of {errors}: {mod.errors}")
    return res, {k: v.get("*", None) for k, v in mod.frames[0].items()}

def test_mlet_s():
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 A \mlet-s|var="x"\*one $name\mlet-e\*B $x
""")
    if v["x"] != "one Fred":
        fail(f"x is {v['x']!r}")
    if "\\v 1 A B one Fred" not in res or "mlet" in res:
        fail(f"Bad output {res}")

def test_mlet_s_paras():
    """ A block across paragraphs. What follows \\mlet-e continues the paragraph
        holding \\mlet-s """
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 Before \mlet-s|var="x"\*one
\p two \bd $name\bd*
\q three\mlet-e\* after
\p Next
""")
    if v["x"] != "one\n\\p two \\bd Fred\\bd*\n\\q three":
        fail(f"x is {v['x']!r}")
    if "\\v 1 Before  after\n\\p Next" not in res or "two" in res:
        fail(f"Bad output {res}")

def test_mlet_s_nested():
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 \mlet-s|var="outer"\*a \mlet-s|var="inner" lang="es"\*b\mlet-e\*$get(inner, es) c\mlet-e\*$outer
""")
    if v["outer"] != "a b c" or v["inner"] is not None:
        fail(f"Variables are {v}")
    if "\\v 1 a b c" not in res:
        fail(f"Bad output {res}")

def test_mlet_s_local():
    """ An \\mlet in a block sets global, unless the name is bound locally """
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 \mlet-s|var="x"\*\mlet|var="y" val="Y"\*$y\mlet-e\*$x $y
""")
    if v["x"] != "Y" or v["y"] != "Y":
        fail(f"Variables are {v}")

@pytest.mark.parametrize("usfm", [
    "\\id GEN test\n\\c 1\n\\p\n\\v 1 A \\mlet-s|var=\"x\"\\* B\n",
    "\\id GEN test\n\\c 1\n\\p\n\\v 1 A \\mlet-e\\* B\n",
])
def test_mlet_s_unmatched(usfm):
    _vars(usfm, errors=1)

def test_runblock():
    """ A block can be run repeatedly with different bindings, leaving it unchanged """
    doc = parseModule(r"""\id GEN module test
\c 1
\p
\v 1 \mlet-s|var="x"\*$who and $name\mlet-e\*
""")
    mod = _mod(doc)
    root = doc.getroot()
    mod._gather(root)
    blk = next(root.iter("ms"))
    res = [mod._usfm(mod._runblock(blk, {"who": w})).strip() for w in ("Jane", "Joe")]
    if res != ["Jane and Fred", "Joe and Fred"]:
        fail(f"Runs gave {res}")
    mod.frames.append({"name": {"*": "Local"}})
    res = [mod._usfm(mod._runblock(blk, {"who": "Jane"}, chain=c)).strip() for c in (True, False)]
    if res != ["Jane and Local", "Jane and Fred"]:
        fail(f"Chained runs gave {res}")
    if blk.text != "$who and $name" or len(mod.frames) != 2:
        fail(f"Block changed to {blk.text!r} or frames left at {len(mod.frames)}")

def test_block_frame():
    """ A block runs in the enclosing frame, so writes to a local stay in it """
    doc = parseModule(r"""\id GEN module test
\c 1
\p
\v 1 \mlet-s|var="x"\*\mlet|var="n" val="$n$n"\*\mlet|var="m" val="M"\*\mlet-e\*
""")
    mod = _mod(doc)
    root = doc.getroot()
    mod._gather(root)
    blk = next(root.iter("ms"))
    local = {"n": {"*": "1"}}
    mod.frames.append(local)
    mod._runblock(blk)
    if local["n"]["*"] != "11" or "m" in local or mod.frames[0].get("m") != {"*": "M"}:
        fail(f"Local frame is {local}, global m is {mod.frames[0].get('m')}")

def test_mfor():
    res, v = _vars("\\id GEN module test\n\\mlet|var=\"xs\" val=\"a\x1cb\x1cc\"\\*\n"
r"""\c 1
\p
\v 1 Start \mfor-s|var="x" list="$xs"\*$x, \mfor-e\*end $name
""")
    if "\\v 1 Start a, b, c, end Fred" not in res or "mfor" in res:
        fail(f"Bad output {res}")
    if "x" in v:
        fail(f"Loop variable left as {v['x']}")

def test_mfor_restore():
    """ The loop variable's previous binding is restored """
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 \mfor-s|var="name" list="Jo"\*$name \mfor-e\*$name
""")
    if "\\v 1 Jo Fred" not in res or v["name"] != "Fred":
        fail(f"Bad output {res} or name {v['name']}")

def test_mfor_empty():
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 A \mfor-s|var="x" list=""\*$x
\p more\mfor-e\*B
""")
    if "\\v 1 A B" not in res or "more" in res:
        fail(f"Bad output {res}")

def test_mfor_paras():
    """ Paragraphs in the block become siblings, what follows \\mfor-e continues
        the last of them, as if the text were substituted """
    res, v = _vars("\\id GEN module test\n\\mlet|var=\"xs\" val=\"a\x1cb\"\\*\n"
r"""\c 1
\p
\v 1 Start \mfor-s|var="x" list="$xs"\*$x
\q \bd $x\bd* \mfor-e\*end
\p Next
""")
    if "\\v 1 Start a\n\\q \\bd a\\bd* b\n\\q \\bd b\\bd* end\n\\p Next" not in res:
        fail(f"Bad output {res}")

def test_mfor_nested():
    res, v = _vars("\\id GEN module test\n\\mlet|var=\"xs\" val=\"a\x1cb\"\\*\n"
r"""\c 1
\p
\v 1 \mfor-s|var="x" list="$xs"\*\mfor-s|var="y" list="$xs"\*
\q $x$y\mfor-e\*\mfor-e\*
\p Next
""")
    if "\\v 1 \n\\q aa\n\\q ab\n\\q ba\n\\q bb\n\\p Next" not in res:
        fail(f"Bad output {res}")

def test_mfor_mlet_s():
    """ A loop runs within an \\mlet-s """
    res, v = _vars("\\id GEN module test\n\\mlet|var=\"xs\" val=\"a\x1cb\"\\*\n"
r"""\c 1
\p
\v 1 \mlet-s|var="out"\*\mfor-s|var="x" list="$xs"\*
\q $x\mfor-e\*\mlet-e\*
""")
    if v["out"] != "\\q a\n\\q b":
        fail(f"out is {v['out']!r}")

def test_mfor_toplevel():
    """ A block between paragraphs adds paragraphs. The paragraph that gathering
        leaves empty, after \\mfor-e, is removed """
    res, v = _vars("\\id GEN module test\n\\c 1\n\\mfor-s|var=\"x\" list=\"a\x1cb\"\\*\n"
r"""\p $x \bd y\bd*
\mfor-e\*
\p after
""")
    if "\\c 1\n\\p a \\bd y\\bd*\n\\p b \\bd y\\bd*\n\\p after" not in res:
        fail(f"Bad output {res}")

def _forlist(lst, attrs, body="$x;"):
    """ Flattens an \\mfor over the list lst, returning the output of verse 1 """
    usfm = ("\\id GEN module test\n\\c 1\n\\p\n\\v 1 \\mfor-s|var=\"x\" list=\"" + lst + "\""
            + attrs + "\\*" + body + "\\mfor-e\\*\n")
    mod = _mod(parseModule(usfm))
    res = mod.flatten().outUsfm(None)
    return res[res.index("\\v 1") + 5:].strip(), mod.errors

@pytest.mark.parametrize("attrs, res", [
    ("", "a;b;c;d;e;"),
    (' slice="1::2"', "b;d;"),
    (' slice="::2"', "a;c;e;"),
    (' slice="-1::"', "e;"),
    (' slice="1:3"', "b;c;"),
    (' slice="::-1"', "e;d;c;b;a;"),
    (' slice="10:"', ""),
])
def test_mfor_slice(attrs, res):
    out, errors = _forlist("a\x1cb\x1cc\x1cd\x1ce", attrs)
    if out != res or errors:
        fail(f"{attrs} gave {out!r} with errors {errors}")

@pytest.mark.parametrize("attrs, res", [
    (' slice="keys"', "one;two;"),
    (' slice="values"', "1;2;"),
])
def test_mfor_dict(attrs, res):
    out, errors = _forlist("one\x1e1\x1ctwo\x1e2", attrs)
    if out != res or errors:
        fail(f"{attrs} gave {out!r} with errors {errors}")

def test_mfor_dict_pair():
    """ A dict item is bound as a [key, value] list """
    doc = parseModule("\\id GEN module test\n\\c 1\n\\p\n\\v 1 \\mfor-s|var=\"x\" list=\"one\x1e1\x1ctwo\x1e2\"\\*"
                   "\\mlet|var=\"last\" val=\"$x\"\\*\\mfor-e\\*\n")
    mod = _mod(doc)
    mod.flatten()
    if mod.frames[0]["last"]["*"] != "two\x1c2" or mod.errors:
        fail(f"Pair bound as {mod.frames[0]['last']} with errors {mod.errors}")

@pytest.mark.parametrize("lst, attrs", [
    ("a\x1cb", ' slice="keys"'),
    ("a\x1cb", ' slice="x"'),
    ("a\x1cb", ' slice="1"'),
    ("a\x1cb", ' slice="a:b"'),
    ("a\x1cb", ' slice="::0"'),
])
def test_mfor_slice_errors(lst, attrs):
    out, errors = _forlist(lst, attrs)
    if len(errors) != 1 or not out.startswith("[ERROR:"):
        fail(f"{attrs} gave {out!r} with errors {errors}")

FS, RS = "\x1c", "\x1e"

@pytest.mark.parametrize("s, res", [
    ("$len($list(a, b, c))", "3"),
    ("$len($list())", "0"),
    ("$len($list(a, $list(b, c), ''))", "3"),
    ("$join(-, a, b)", "a-b"),
    ("$join(-, $list(a, b), c)", "a-b-c"),
    ("$join(' ', $split('x y z', ' '))", "x y z"),
    ("$join(;, $split('a,b,c'))", "a;b;c"),
    ("$len($split(''))", "0"),
    ("$join(;, $strip($split('a , b')))", "a;b"),
    ("$join(;, $range(3))", "0;1;2"),
    ("$join(;, $range(1, 4))", "1;2;3"),
    ("$join(;, $range(10, 0, -3))", "10;7;4;1"),
    ("$iget($list(a, b, c), 1)", "b"),
    ("$iget($list(a, b, c), -1)", "c"),
    ("$iget($list(a, b), 5, none)", "none"),
    ("$iget($dict($list(one, 1, two, 2)), two)", "2"),
    ("$iget($dict($list(one, two), $list(1, 2)), one)", "1"),
    ("$iget($dict($list(one, two), x), two)", "x"),
    ("$iget($dict($list(one, 1)), three, none)", "none"),
    ("$len($dict($list(one, 1, two, 2)))", "2"),
])
def test_listfns(s, res):
    _e(s, res)

@pytest.mark.parametrize("s, res", [
    ("$dict($list(one, 1, two))", "[ERROR: $dict needs a value for each key]"),
    ("$dict($list(a, b, c), $list(1, 2))", "[ERROR: $dict has 3 keys and 2 values]"),
    ("$iget($list(a, b), 2)", "[ERROR: No item '2']"),
    ("$iget($list(a, b), x)", "[ERROR: $iget needs a number, not 'x']"),
    ("$range(a)", "[ERROR: $range needs a number, not 'a']"),
    ("$range(1, 2, 0)", "[ERROR: $range step is 0]"),
    ("$range()", "[ERROR: Wrong number of arguments (0) to $range]"),
    ("$list(a, b)", "[ERROR: A list can't be output, use $join()]"),
    ("$dict($list(a, b))", "[ERROR: A list can't be output, use $join()]"),
])
def test_listfn_errors(s, res):
    _e(s, res, errors=1)

def test_list_leak_attrib():
    """ A list can't go in an attribute either """
    res = _flatten(r"""\id GEN module test
\c 1
\p
\v 1 \w word|lemma="$list(a, b)"\w*
""", errors=1)
    if "[ERROR: A list" not in res:
        fail(f"Bad output {res}")

def test_mfor_dict_iget():
    out, errors = _forlist("$dict($list(one, 1, two, 2))", "", "$iget($x, 0)=$iget($x, 1);")
    if out != "one=1;two=2;" or errors:
        fail(f"Gave {out!r} with errors {errors}")

def _mdoc(body):
    return "\\id GEN module test\n" + body

def test_mdef():
    res, v = _vars(_mdoc(r"""\c 1
\p
\v 1 $greet(Jane). $greet(Joe, Bloggs).
\mdef-s|name="greet" args="who, family..."\*
    Hello $who
\mdef-e\*
\p $greet()
"""), errors=1)
    if "\\v 1 Hello Jane. Hello Joe." not in res or "mdef" in res:
        fail(f"Bad output {res}")
    if "[ERROR: Wrong number of arguments (0) to $greet]" not in res:
        fail(f"No arity error in {res}")

def test_mdef_rest():
    res, v = _vars(_mdoc(r"""\mdef-s|name="all" args="first, rest…"\*$first: $join(+, $rest) ($len($rest))\mdef-e\*
\c 1
\p
\v 1 $all(a, b, c) $all(a)
"""))
    if "\\v 1 a: b+c (2) a:  (0)" not in res:
        fail(f"Bad output {res}")

def test_mdef_arity():
    res, v = _vars(_mdoc(r"""\mdef-s|name="two" args="a, b"\*$a$b\mdef-e\*
\c 1
\p
\v 1 $two(x) $two(x, y) $two(x, y, z)
"""), errors=2)
    if "[ERROR: Wrong number of arguments (1) to $two] xy [ERROR: Wrong number of arguments (3) to $two]" not in res:
        fail(f"Bad output {res}")

def test_mdef_frames():
    """ A macro sees its parameters and globals, not its caller's parameters.
        Writes to a parameter stay local, others go global. """
    res, v = _vars(_mdoc(r"""\mdef-s|name="inner" args=""\*[$p $name]\mdef-e\*
\mdef-s|name="outer" args="p"\*$inner()\mlet|var="p" val="changed"\*\mlet|var="g" val="$p"\*\mdef-e\*
\c 1
\p
\v 1 $outer(local) $p
"""))
    if "\\v 1 [$p Fred] $p" not in res:
        fail(f"Bad output {res}")
    if v.get("g") != "changed" or "p" in v:
        fail(f"Globals are {v}")

def test_mdef_args_evaluated():
    """ Arguments are evaluated by the caller and bound, not re-expanded """
    res, v = _vars(_mdoc(r"""\mdef-s|name="show" args="x"\*<$x>\mdef-e\*
\mdef-s|name="pass" args="name"\*$show($name)\mdef-e\*
\c 1
\p
\v 1 $pass(Jane) $show('$name') $show($$name)
"""))
    if "\\v 1 <Jane> <$name> <$name>" not in res:
        fail(f"Bad output {res}")

def test_mdef_blocks():
    """ A macro can hold paragraphs and blocks, and returns them as USFM text.
        The rest of the \\li holding \\mfor-e, left empty by gathering, is removed """
    res, v = _vars(_mdoc("\\mlet|var=\"xs\" val=\"a\x1cb\"\\*\n" + r"""\mdef-s|name="items" args="pre"\*
\mfor-s|var="x" list="$xs"\*
\li $pre $x\mfor-e\*
\mdef-e\*
\c 1
\p
\v 1 \mlet|var="out" val="$items(-)"\*
"""))
    if v["out"] != "\\li - a\n\\li - b":
        fail(f"out is {v['out']!r}")

def test_mdef_redefine():
    res, v = _vars(_mdoc(r"""\mdef-s|name="m" args=""\*one\mdef-e\*
\mdef-s|name="m" args=""\*two\mdef-e\*
\mdef-s|name="s" args=""\*three\mdef-e\*
\c 1
\p
\v 1 $m()
"""), errors=2)
    if "\\v 1 one" not in res:
        fail(f"Bad output {res}")

@pytest.mark.parametrize("attrs", ['name="" args=""', 'name="a b" args=""', 'name="m" args="a, b c"',
                                   'name="m" args="a…, b"'])
def test_mdef_bad(attrs):
    _vars(_mdoc("\\mdef-s|" + attrs + "\\*x\\mdef-e\\*\n\\c 1\n\\p\n\\v 1 text\n"), errors=1)

def test_mdef_nested():
    mod = _mod(parseModule(_mdoc(r"""\c 1
\p
\v 1 \mfor-s|var="x" list="a"\*\mdef-s|name="m" args=""\*one\mdef-e\*\mfor-e\*
""")))
    res = mod.flatten().outUsfm(None)
    if len(mod.errors) != 1 or not mod.errors[0][0].startswith("\\mdef-s must be at the top level") \
            or "one" in res:
        fail(f"Errors {mod.errors} in {res}")

def test_mdef_recursion():
    mod = _mod(parseModule(_mdoc(r"""\mdef-s|name="loop" args="x"\*$loop($x)\mdef-e\*
\c 1
\p
\v 1 $loop(a)
""")))
    with pytest.raises(ModuleFatalError):
        mod.flatten()

def _errors(usfm):
    mod = _mod(parseModule(usfm))
    mod.flatten()
    return mod.errors

def test_error_lines():
    """ Errors give the module line of the expression """
    errs = _errors(r"""\id GEN module test
\mdef-s|name="m" args=""\*
  x
\mdef-e\*
\c 1
\p
\v 1 First $s()
then $s(GEN 1:1, a, b) and
\mfor-s|var="x" list="a"\*
\q $s()
\mfor-e\* after
and $s()
\p \w word|lemma="$list(a, b)"\w*
""")
    if [e[1] for e in errs] != [7, 8, 10, 12, 13]:
        fail(f"Lines are wrong: {errs}")

@pytest.mark.parametrize("usfm, msg", [
    ("\\v 1 $join(;, $iget($list(a), 5))",
        "No item '5'; in $iget($list(a), 5); in $join"),
    ("\\v 1 \\mlet|var=\"xs\" val=\"$list(a, b)\"\\*$xs",
        "A list can't be output, use $join(); in $xs"),
    ("\\v 1 \\mlet|var=\"y\" val=\"$iget($name, q)\"\\*",
        "$iget needs a number, not 'q'; in $iget($name, q); in val=\"$iget($name, q)\"; in \\mlet"),
    ("\\v 1 \\w word|lemma=\"$list(a, b)\"\\w*",
        "A list can't be output, use $join(); in $list(a, b); in lemma of \\w"),
    ("\\v 1 \\mfor-s|var=\"x\" list=\"$list(a, b)\"\\*$s($x)\\mfor-e\\*",
        "Bad reference 'b': "),
])
def test_error_context(usfm, msg):
    errs = _errors("\\id GEN module test\n\\c 1\n\\p\n" + usfm + "\n")
    if not errs or not errs[-1][0].startswith(msg) or errs[-1][1] != 4:
        fail(f"Errors are {errs}, expected {msg!r} on line 4")

def test_error_active():
    """ Errors within macros and loops say how they were reached """
    errs = _errors(r"""\id GEN module test
\mdef-s|name="m" args="x"\*$iget($x, 3)\mdef-e\*
\c 1
\p
\v 1 \mfor-s|var="k" list="$list(a, b)"\*
$m($k)\mfor-e\*
""")
    msgs = [e[0] for e in errs]
    if msgs != ["No item '3'; in $iget($x, 3); in macro $m called at line 6; in \\mfor-s at line 5 with $k='a' (item 0)",
                "No item '3'; in $iget($x, 3); in macro $m called at line 6; in \\mfor-s at line 5 with $k='b' (item 1)"] \
            or [e[1] for e in errs] != [2, 2]:
        fail(f"Errors are {errs}")

def _outdoc(usfm, errors=0):
    """ Flattens usfm, returning the USFM and the flattened document """
    mod = _mod(parseModule(usfm))
    doc = mod.flatten()
    if len(mod.errors) != errors:
        fail(f"{len(mod.errors)} errors instead of {errors}: {mod.errors}")
    return doc.outUsfm(None), doc.getroot()

_heads = r"""\id GEN module test
\mdef-s|name="head" args="t"\*
\s $t
\mdef-e\*
\mdef-s|name="b" args="t"\*\bd $t\bd*\mdef-e\*
\mdef-s|name="cash" args=""\*\bd $$name\bd*\mdef-e\*
\c 1
"""

def test_output_inline():
    """ Markup in an output value becomes elements, keeping the spaces around it """
    res, root = _outdoc(_heads + "\\p\n\\v 1 a $b(x) c $b(y)\n")
    if "\\v 1 a \\bd x\\bd* c \\bd y\\bd*" not in res:
        fail(f"Bad output {res}")
    if [c.get("style") for c in root.iter("char")] != ["bd", "bd"]:
        fail(f"No char elements in {res}")

def test_output_blocks():
    """ Paragraphs in an output value split the paragraph """
    res, root = _outdoc(_heads + "\\p\n\\v 1 Before $head(Intro) after \\bd b\\bd*\n\\p Next $head(Two)\n")
    if "\\v 1 Before\n\\s Intro after \\bd b\\bd*\n\\p Next\n\\s Two" not in res:
        fail(f"Bad output {res}")
    styles = [p.get("style") for p in root.iter("para")][-4:]     # after any left by \\mdef-e
    if styles != ["p", "s", "p", "s"]:
        fail(f"Paragraphs are {styles} in {res}")

def test_output_tail():
    """ Output in a tail, after a milestone that is removed """
    res, root = _outdoc(_heads + "\\p\n\\v 1 a\\mlet|var=\"x\" val=\"y\"\\* $head($x) z\n")
    if "\\v 1 a\n\\s y z" not in res:
        fail(f"Bad output {res}")

def test_output_variable():
    """ A captured block output from a variable becomes paragraphs """
    res, root = _outdoc(r"""\id GEN module test
\mlet-s|var="blk"\*
\q one \bd $name\bd*
\q two
\mlet-e\*
\c 1
\p
\v 1 Then $blk
\p after
""")
    if [(p.get("style"), p.text) for p in root.iter("para")][-3:] != [("q", "one "), ("q", "two"), ("p", "after\n")]:
        fail(f"Bad output {res}")

def test_output_noreexpand():
    """ A $ in an output value is not expanded again """
    res, root = _outdoc(_heads + "\\p\n\\v 1 $cash()\n")
    if "\\v 1 \\bd $name\\bd*" not in res:
        fail(f"Bad output {res}")

def test_output_plain_backslash():
    """ Only values are markup: a backslash in an error marker stays text """
    mod = Module(parseModule(_heads + "\\p\n\\v 1 $s($bs) $b(y)\n"),
                 envs={"*": bkenv}, variables={"bs": "\\q"})
    doc = mod.flatten()
    res, root = doc.outUsfm(None), doc.getroot()
    if len(mod.errors) != 1 or len(list(root.iter("char"))) != 1 \
            or "Bad reference '\\\\q'" not in "".join(root.itertext()):
        fail(f"Bad output {res}")

def test_output_noroom():
    """ Paragraphs can't go inside a character style """
    res, root = _outdoc(_heads + "\\p\n\\v 1 \\bd $head(x)\\bd*\n", errors=1)
    if list(root.iter("char"))[0].text != "\\s x":
        fail(f"Bad output {res}")

@pytest.mark.parametrize("s, res", [
    ("$op(+, 1, 2, 3)", "6"),
    ("$op(+, 1.5, 2)", "3.5"),
    ("$op(+, a, 1)", "a1"),
    ("$join(;, $op(+, $list(a, b), c))", "a;b;c"),
    ("$op(-, 10, 3, 2)", "5"),
    ("$op(*, 2, 3)", "6"),
    ("$op(*, ab, 3)", "ababab"),
    ("$join(;, $op(*, $list(a, b), 2))", "a;b;a;b"),
    ("$op(/, 4, 2)", "2"),
    ("$op(/, 1, 4)", "0.25"),
    ("$op(//, 7, 2)", "3"),
    ("$op(%, 7, 3)", "1"),
    ("$op(%, -1, 7)", "6"),
    ("$op(<, 3, 10)", "1"),
    ("$op(<, -3, 2)", "1"),
    ("$op(<, 3fred, 10fred)", "1"),
    ("$op(>, b, a)", "1"),
    ("$op(=, 2, 2.0)", "1"),
    ("$op(=, abc, abc)", "1"),
    ("$op(!=, abc, abd)", "1"),
    ("$op(=, abc, abd)", "0"),
    ("$bool(Yes)", "1"),
    ("$bool(maybe)", "1"),
    ("$bool(No)", "0"),
    ("$bool('')", "0"),
    ("$not(0)", "1"),
    ("$not(x)", "0"),
    ("$and(1, yes, x)", "1"),
    ("$and(1, no)", "0"),
    ("$or('', F, 1)", "1"),
    ("$or('', false)", "0"),
    ("$if(1, a, b)", "a"),
    ("$if(0, a, b)", "b"),
    ("$if(0, a)", ""),
    ("$if($op(<, 1, 2), yes, no)", "yes"),
])
def test_ops(s, res):
    _e(s, res)

@pytest.mark.parametrize("s, res", [
    ("$op(-, a, 1)", "[ERROR: $op(-) needs numbers, not 'a']"),
    ("$op(/, 1, 0)", "[ERROR: $op(/) divides by 0]"),
    ("$op(*, a, 1.5)", "[ERROR: $op(*) repeats a string a whole number of times]"),
    ("$op(<, 1, 2, 3)", "[ERROR: $op(<) compares 2 values, not 3]"),
    ("$op(^, 1, 2)", "[ERROR: Unknown operator '^']"),
    ("$op(+)", "[ERROR: $op(+) has no values]"),
])
def test_op_errors(s, res):
    _e(s, res, errors=1)

def test_lazy():
    """ $if, $and and $or only evaluate what they need """
    _e("$if(1, ok, $s()) $if(0, $s(), ok) $and(0, $s()) $or(1, $s())", "ok ok 0 1")
    _e("$if(1, $s(), ok)", "[ERROR: Wrong number of arguments (0) to $s]", errors=1)

def test_lazy_recursion():
    """ A macro can recurse, stopped by $if, since the unchosen branch is not evaluated """
    res, v = _vars(_mdoc(r"""\mdef-s|name="count" args="n"\*$if($op(>, $n, 0), $n $count($op(-, $n, 1)), go)\mdef-e\*
\c 1
\p
\v 1 $count(3)
"""))
    if "\\v 1 3 2 1 go" not in res:
        fail(f"Bad output {res}")

def test_mif():
    res, v = _vars(_mdoc(r"""\c 1
\p
\v 1 \mif-s|cond="$op(=, $name, Fred)"\*yes $name\melse\*no\mif-e\* \mif-s|cond="0"\*yes\melse\*no\mif-e\* \mif-s|cond="0"\*yes\mif-e\*end
"""))
    if "\\v 1 yes Fred no end" not in res or "mif" in res or "melse" in res:
        fail(f"Bad output {res}")

def test_mif_paras():
    """ The branches can hold paragraphs, and only the chosen one is run """
    for cond, out, x in (("1", "\\q a\n\\q b after", "A"), ("0", "\\q c after", "C")):
        res, v = _vars(_mdoc(r"""\c 1
\p
\v 1 \mif-s|cond="%s"\*
\q a\mlet|var="x" val="A"\*
\q b\melse\*
\q c\mlet|var="x" val="C"\*\mif-e\* after
\p Next
""" % cond))
        if out not in res or "\\p Next" not in res or v.get("x") != x:
            fail(f"cond={cond}: bad output {res} x={v.get('x')}")

def test_mif_nested():
    res, v = _vars(_mdoc(r"""\c 1
\p
\v 1 \mif-s|cond="1"\*\mif-s|cond="0"\*a\melse\*b\mif-e\* c\melse\*d\mif-e\*
"""))
    if "\\v 1 b c" not in res:
        fail(f"Bad output {res}")

def test_mif_in_loop():
    res, v = _vars(_mdoc(r"""\c 1
\p
\v 1 \mfor-s|var="x" list="$range(4)"\*\mif-s|cond="$op(%, $x, 2)"\*odd\melse\*even\mif-e\* \mfor-e\*
"""))
    if "\\v 1 even odd even odd" not in res:
        fail(f"Bad output {res}")

@pytest.mark.parametrize("body", ["\\melse\\* x", "\\mif-s|cond=\"1\"\\*a\\melse\\*b\\melse\\*c\\mif-e\\*",
                                  "\\mif-s|cond=\"1\"\\*\\mfor-s|var=\"x\" list=\"a\"\\*\\melse\\*\\mfor-e\\*\\mif-e\\*"])
def test_melse_unexpected(body):
    res, v = _vars(_mdoc("\\c 1\n\\p\n\\v 1 " + body + "\n"), errors=1)
    if "melse" in res:
        fail(f"Bad output {res}")

def test_example_rt(tmp_path):
    """ The Text + Reference example from the spec: a macro heading each reading
        with its reference, followed by the reading """
    res, root, errors = _mref(tmp_path, r"""\id FRT module test
\mdef-s|name="rt" args="reft"\*
\r $s($reft)
\mref|$reft\*
\mdef-e\*

$rt(JON 1:1-2)
$rt(JON 2:1)
""")
    heads = [p.text.strip() for p in root.iter("para") if p.get("style") == "r" and p.text and p.text.strip()]
    if heads != ["Jonah 1:1-2", "Jonah 2:1"] or errors:
        fail(f"Headings are {heads} in {res} with {errors}")
    verses = [v.get("number") for v in root.iter("verse")]
    if verses != ["1", "2", "1"] or "$" in res or "\\mref" in res:
        fail(f"Verses are {verses} in {res}")

@pytest.mark.parametrize("s, res", [
    ("$e('$name')", "Fred"),
    ("$e('$s($ref)')", "Judges 3:4"),
    ("$e($$name)", "Fred"),
    ("$e('$$name')", "$name"),
    ("$e('a $nobody b')", "a $nobody b"),
    ("$e(plain)", "plain"),
])
def test_e(s, res):
    _e(s, res)

def test_e_error():
    mod = _mod()
    out = mod.expand("$e('$s()')")
    if out != "[ERROR: Wrong number of arguments (0) to $s]" or len(mod.errors) != 1 \
            or "in $s(); in $e" not in mod.errors[0][0]:
        fail(f"Gave {out!r} with errors {mod.errors}")

def test_computed_names():
    res, v = _vars(_mdoc(r"""\mdef-s|name="greet" args="who"\*Hello $who\mdef-e\*
\mlet|var="fn" val="s"\*
\mlet|var="mac" val="greet"\*
\mlet|var="which" val="name"\*
\mlet|var="title_es" val="Léxico"\*
\mlet|var="lang" val="es"\*
\c 1
\p
\v 1 ${$fn}(JHN 3:16); ${$mac}(Jo); ${$which}; ${title_$lang}; ${name}(x); ${$fn
"""))
    # an unclosed ${ is a literal $, so what follows it is still expanded
    if "\\v 1 John 3:16; Hello Jo; Fred; Léxico; Fred(x); ${s" not in res:
        fail(f"Bad output {res}")

@pytest.mark.parametrize("s, res", [
    ("${$name}(x)", "[ERROR: No function or macro $Fred]"),
    ("${$title}", "[ERROR: No value for $Lexicon]"),
    ("${a b}", "[ERROR: Bad name 'a b']"),
    ("${$s(x}", "[ERROR: Missing ) in call to $s]"),
])
def test_computed_name_errors(s, res):
    _e(s, res, errors=1)

def _isets(lines, init=None, errors=0):
    """ Runs \\miset lines on variable x, returning its items """
    usfm = _mdoc(("\\mlet|var=\"x\" val=\"" + init + "\"\\*\n" if init is not None else "")
                 + "".join(f"\\miset|var=\"x\" {l}\\*\n" for l in lines) + "\\c 1\n\\p\n\\v 1 x\n")
    res, v = _vars(usfm, errors=errors)
    return v.get("x", None)

@pytest.mark.parametrize("init, lines, res", [
    ("a\x1cb\x1cc", ['index="1" val="B"'], "a\x1cB\x1cc"),
    ("a\x1cb\x1cc", ['index="-1" val="C"'], "a\x1cb\x1cC"),
    ("a\x1cb", ['index="2" val="c"'], "a\x1cb\x1cc"),
    ("a", ['index="3" val="d"'], "a\x1c\x1c\x1cd"),
    (None, ['index="0" val="a"', 'index="1" val="b"'], "a\x1cb"),
    (None, ['index="k" val="v"', 'index="j" val="w"', 'index="k" val="V"'], "k\x1eV\x1cj\x1ew"),
    ("k\x1ev", ['index="1" val="one"'], "k\x1ev\x1c1\x1eone"),
    ("a\x1cb", ['index="$op(+, 0, 1)" val="$name"'], "a\x1cFred"),
])
def test_miset(init, lines, res):
    if (v := _isets(lines, init)) != res:
        fail(f"x is {v!r} not {res!r}")

@pytest.mark.parametrize("init, line", [
    ("a\x1cb", 'index="k" val="v"'),               # a list has no keys
    ("a\x1cb", 'index="-3" val="v"'),              # before the start
    ("a\x1cb", 'index="0" val="$list(c, d)"'),     # an item can't be a list
    ("a\x1cb", 'val="v"'),                         # no index
])
def test_miset_errors(init, line):
    if (v := _isets([line], init, errors=1)) != init:
        fail(f"x changed to {v!r}")

def test_miset_block():
    res, v = _vars(_mdoc(r"""\c 1
\p
\v 1 \mfor-s|var="k" list="$list(a, b)"\*\miset-s|var="d" index="$k"\*\bd $k\bd*\miset-e\*\mfor-e\*$iget($d, b)
"""))
    if v["d"] != "a\x1e\\bd a\\bd*\x1cb\x1e\\bd b\\bd*" or "\\v 1 \\bd b\\bd*" not in res:
        fail(f"d is {v['d']!r} in {res}")

@pytest.mark.parametrize("s, res", [
    ("$sub(a1b22, '\\d+', '[\\g<0>]')", "a[1]b[22]"),
    ("$sub('x;y;', ';$', '')", "x;y"),
    ("$sub(abc, '(b)', '<\\1>')", "a<b>c"),
])
def test_sub(s, res):
    _e(s, res)

def test_sub_usfm():
    """ Backslashes in quoted arguments are as written, not USFM markers """
    res = _flatten(_mdoc(r"""\c 1
\p
\v 1 $sub(a1b22, '\d+', '<\g<0>>') \mlet|var="y" val="$sub(ab, '(\w)', '[\1]')"\*$y
"""))
    if "\\v 1 a<1>b<22> [a][b]" not in res:
        fail(f"Bad output {res}")

def test_sub_error():
    _e("$sub(a, '(', x)", "[ERROR: Bad regex or replacement in $sub: missing ), unterminated subpattern at position 0]", errors=1)

@pytest.mark.parametrize("src, res", [
    (r"$f('\d', "+'"'+r"\w"+'"'+r", \x)", r"$f('\\d', "+'"'+r"\\w"+'"'+r", \x)"),   # quoted only
    (r"$f(a, $g( '\d' ), John's \v)", r"$f(a, $g( '\\d' ), John's \v)"),          # at the start of an argument
    (r"$${x}('\d') $$f('\d')", r"$${x}('\d') $$f('\d')"),                        # $$ is not a call
    (r"${$fn}('\d')", r"${$fn}('\\d')"),
    (r"(x) '\d' $# note \bd" + "\n" + r"'\d'", r"(x) '\d' $# note \\bd" + "\n" + r"'\d'"),
    (r"$f('\d", r"$f('\d"),                                                      # unterminated
])
def test_protect(src, res):
    if (out := protect(src)) != res:
        fail(f"{src!r} protected to {out!r}")

def test_quoted_markers():
    """ A marker in a quoted argument is an inert string, until it is output """
    res, root = _outdoc(_mdoc(r"""\c 1
\p
\v 1 $if(1, '\bd bold\bd*', no) $len($split('a\q b', '\q')) $# a \d comment
\p next
"""))
    if "\\v 1 \\bd bold\\bd* 2\n\\p next" not in res:
        fail(f"Bad output {res}")

@pytest.mark.parametrize("s, res", [
    ("$a(JHN 3:16)", "Jn 3:16"),
    ("$s(JHN 3:16)", "John 3:16"),
    ("$l(JHN 3:16)", "The Gospel According to John 3:16"),
    ("$s(Jn 3:16-18; Rom 1)", "John 3:16-18; Romans 1"),
    ("$r(John 3:16)", "JHN 3:16"),
    ("$r(Jn 3:16-18; Rom 1)", "JHN 3:16-18; ROM 1"),
    ("$r('Jn 3:16-18; Rom 1', last)", "ROM 1"),
    ("$r('Jn 3:16-18; Rom 1', 0)", "JHN 3:16-18"),
    ("$r('Jn 3:16-18; Rom 1', -2.first)", "JHN 3:16"),
    ("$r('Jn 3:16-18; Rom 1', 0.last.verse)", "18"),
    ("$r('Jn 3:16-18; Rom 1', last.last)", "ROM 1:32"),
    ("$r('Jn 3:16-18; Rom 1', book)", "ROM"),
    ("$r('Jn 3:16-18; Rom 1', first.chapter)", "3"),
    ("$r('JHN 3:16-4:2', last.chapter)", "4"),
    ("$r('MAT 5:3a', verse)", "3a"),
    ("$s($r(Judges 3:4))", "Judges 3:4"),
])
def test_reffns(s, res):
    _e(s, res)

@pytest.mark.parametrize("s, res", [
    ("$r('JHN 3:16', 1)", "[ERROR: No range 1 in JHN 3:16]"),
    ("$r('JHN 3:16', chapter.verse)", "[ERROR: Nothing can follow a part in $r path 'chapter.verse']"),
    ("$r('JHN 3:16', page)", "[ERROR: Bad part 'page' in $r path 'page']"),
    ("$r('JHN 3:16', last.1)", "[ERROR: Bad part '1' in $r path 'last.1']"),
    ("$r(Nowhere 3)", "[ERROR: Bad reference 'Nowhere 3': Illegal book name: Nowhere]"),
])
def test_reffn_errors(s, res):
    _e(s, res, errors=1)

def test_ref_spacedbook():
    """ Local book names can contain spaces, so $s output parses back """
    _e("$r(1 John 1:1) $r($s(1JN 1:1)) $r($l(SNG 2:1))", "1JN 1:1 1JN 1:1 SNG 2:1")

def test_ref_lang():
    """ The lang argument, else $LANG, chooses the environment """
    fr = BookNamesEnvironment()
    fr.addBookName("JHN", "Jn", "Jean", "Évangile selon Jean")
    mod = Module(parseModule(_mdoc(r"""\c 1
\p
\v 1 $s(JHN 3:16, fr) $r(Jean 3:16, '', fr) $s(JHN 3:16) \mlet|var="LANG" val="fr"\*$s(JHN 3:16) $a(JHN 3:16, en)
""")), envs={"*": bkenv, "fr": fr})
    res = mod.flatten().outUsfm(None)
    if "\\v 1 Jean 3:16 JHN 3:16 John 3:16 Jean 3:16 Jn 3:16" not in res or mod.errors:
        fail(f"Bad output {res} with {mod.errors}")

@pytest.mark.parametrize("s, res", [
    ("$match(abc, b)", "1"),
    ("$match(abc, '^b')", "0"),
    ("$join(;, $match(a12b, '(\\d)(\\d)'))", "12;1;2"),
    ("$iget($match('key=val', '(\\w+)=(\\w*)'), 2)", "val"),
    ("$len($match(abc, '(x)'))", "0"),
    ("$join(;, $match(ab, '(a)(x)?'))", "a;a;"),
    ("$if($match(abc, '(b)'), yes, no)", "yes"),
])
def test_match(s, res):
    _e(s, res)

def test_match_error():
    _e("$match(a, '(')", "[ERROR: Bad regex in $match: missing ), unterminated subpattern at position 0]", errors=1)

@pytest.mark.parametrize("s, res", [
    ("JHN 3:16; ROM 1", ["JHN 3:16", "ROM 1"]),
    ("JHN 1:1-3, v", ["JHN 1:1", "JHN 1:2", "JHN 1:3"]),
    ("GEN-LEV, b", ["GEN", "EXO", "LEV"]),
    ("GEN 50:3-EXO 1:3, b", ["GEN 50:3-26", "EXO 1:1-3"]),
    ("JHN 1:50-3:1, c", ["JHN 1:50-51", "JHN 2", "JHN 3:1"]),
    ("JUD 24-25, v", ["JUD 24", "JUD 25"]),
    ("'', v", [""]),
])
def test_rall(s, res):
    _e(f"$join(;, $rall({s}))", ";".join(res))

def test_rall_errors():
    _e("$rall(JHN 1, x)", "[ERROR: Bad level 'x' to $rall]", errors=1)

def test_mfor_rall():
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 \mfor-s|var="r" list="$rall(JHN 3:16-17, v)"\*$s($r); \mfor-e\*
""")
    if "\\v 1 John 3:16; John 3:17;" not in res:
        fail(f"Bad output {res}")

def _project(root, name, lang="en:::", booknames=True, **kw):
    """ A project directory holding Jonah """
    import shutil
    path = os.path.join(root, name)
    os.makedirs(path)
    vals = {"LanguageIsoCode": lang, "Versification": "4", "FileNameBookNameForm": "41MAT",
            "FileNamePrePart": "", "FileNamePostPart": name + ".usfm"}
    vals.update(kw)
    with open(os.path.join(path, "Settings.xml"), "w", encoding="utf-8") as outf:
        outf.write("<ScriptureText>" + "".join(f"<{k}>{v}</{k}>" for k, v in vals.items()) + "</ScriptureText>")
    testdir = os.path.dirname(__file__)
    shutil.copy(os.path.join(testdir, "32JONBSB.usfm"), os.path.join(path, "32JON" + name + ".usfm"))
    if booknames:
        shutil.copy(os.path.join(testdir, "BookNames.xml"), os.path.join(path, "BookNames.xml"))

def _projects(root):
    from usfmtc.projects import Projects
    _project(root, "TST", ChapterVerseSeparator=".")
    _project(root, "FRA", lang="fr:::", booknames=False)
    return Projects(root)

def test_project(tmp_path):
    projects = _projects(str(tmp_path))
    mod = Module(None, project=projects.find("TST"), projects=projects)
    assert mod.lang == "en"
    assert mod.expand("$s(JON 1:1)") == "Jonah 1.1"         # the project's names and separators
    assert mod.expand("$s(JON 1:1, fr)") == "JON 1:1"       # no fr names, so canonical
    assert Module(None, project=projects.find("TST"), lang="fr").lang == "fr"

def test_project_lang(tmp_path):
    """ $LANG starts as the module's language """
    projects = _projects(str(tmp_path))
    tst = projects.find("TST")
    assert Module(None, project=tst).expand("$LANG") == "en"
    assert Module(None, project=tst, lang="fr").expand("$LANG") == "fr"
    assert Module(None, project=tst, variables={"LANG": "de"}).expand("$LANG") == "de"
    assert Module(None, lang="fr").expand("$LANG") == "fr"
    assert Module(None).expand("$LANG") == "$LANG"      # no language at all

def test_project_tocnames(tmp_path):
    """ A project without BookNames.xml names its books from \\toc """
    projects = _projects(str(tmp_path))
    mod = Module(None, project=projects.find("FRA"), projects=projects)
    assert mod.lang == "fr"
    assert mod.expand("$l(JON 1:1)") == "Jonah 1:1"

def test_project_lookup(tmp_path):
    projects = _projects(str(tmp_path))
    tst = projects.find("TST")
    mod = Module(None, project=tst, projects=projects)
    assert mod._project(None) is tst
    assert mod._project("fr+FRA") is projects.find("FRA")
    with pytest.raises(ModuleError, match="No project for en\\+XYZ"):
        mod._project("en+XYZ")
    with pytest.raises(ModuleError, match="No project to take scripture"):
        Module(None)._project(None)

def test_cli_project(tmp_path, monkeypatch):
    _projects(str(tmp_path / "prjs"))
    infile = tmp_path / "mod.usfm"
    infile.write_text("\\id FRT\n\\p $s(JON 1:1)\n", encoding="utf-8")
    outfile = tmp_path / "out.usfm"
    assert main(["-R", str(tmp_path / "prjs"), "-p", "TST", str(infile), str(outfile)]) == 0
    assert "Jonah 1.1" in outfile.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path / "prjs")                    # the default projects directory
    assert main(["-p", "fra", str(infile), str(outfile)]) == 0
    assert "Jonah 1:1" in outfile.read_text(encoding="utf-8")
    infile.write_text("\\id FRT\n\\p $LANG\n", encoding="utf-8")
    assert main(["-p", "fra", str(infile), str(outfile)]) == 0
    assert "\\p fr" in outfile.read_text(encoding="utf-8")
    assert main(["-p", "fra", "-l", "wsg", str(infile), str(outfile)]) == 0
    assert "\\p wsg" in outfile.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["-p", "XYZ", str(infile), str(outfile)])

def test_flattenmodulefile(tmp_path):
    from usfmtc.projects import Projects
    projects = _projects(str(tmp_path / "prjs"))
    infile = tmp_path / "mod.usfm"
    infile.write_text("\\id FRT\n\\p $s(JON 1:1) $LANG $x $s(JON 1:1, a, b)\n", encoding="utf-8")
    errors = []
    res = flattenModuleFile(str(infile), project="TST", projects=str(tmp_path / "prjs"),
                            variables={"x": "X"}, moderrors=errors)
    out = res.outUsfm()
    assert "Jonah 1.1 en X" in out
    assert "[ERROR: Wrong number of arguments (3) to $s]" in out
    assert len(errors) == 1 and errors[0][1] == 2
    res = flattenModuleFile(str(infile), project=projects.find("FRA"), lang="de",
                            booknames=os.path.join(os.path.dirname(__file__), "BookNames.xml"))
    assert "John" not in res.outUsfm() and "Jonah 1:1 de" in res.outUsfm()
    with pytest.raises(ValueError, match="No project XYZ"):
        flattenModuleFile(str(infile), project="XYZ", projects=[str(tmp_path / "prjs")])
    with pytest.raises(ValueError, match="Can't read"):
        flattenModuleFile(str(tmp_path / "mod.abc"))

def test_flattenmodulefile_usx(tmp_path):
    """ A module saved as USX is read as USX """
    projects = _projects(str(tmp_path / "prjs"))
    usx = tmp_path / "mod.usx"
    parseModule("\\id FRT\n\\p $s(JON 1:1)\n").saveAs(str(usx))
    res = flattenModuleFile(str(usx), project=projects.find("TST"))
    assert "Jonah 1.1" in res.outUsfm()

def test_flattenmodulefile_options(tmp_path):
    """ One bundle of options goes to both readFile and Module """
    projects = _projects(str(tmp_path / "prjs"))
    infile = tmp_path / "mod.mod"
    infile.write_text("﻿\\id FRT\n\\p $sub(a1b2, '\\d', '#') $LANG $s(JON 1:1)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Can't read"):
        flattenModuleFile(str(infile), project=projects.find("TST"))
    res = flattenModuleFile(str(infile), informat="usfm", strict=False, lang="fr",
                            envs={"fr": bkenv}, project=projects.find("TST"))
    assert res.book == "FRT"
    assert "a#b# fr Jonah 1:1" in res.outUsfm()

_jon13 = ("Nevertheless, the men rowed hard to get back to dry land, but they could not, "
          "for the sea was raging against them more and more.")
_jon16 = ("Then the men feared the LORD greatly, and they offered a sacrifice to the LORD "
          "and made vows to Him.")

@pytest.mark.parametrize("s, res", [
    ("$reftext(JON 1:13)", _jon13),
    ("$reftext(Jonah 1:13)", _jon13),                     # the module's book names
    ("$reftext('JON 1:13; 16')", _jon13 + " " + _jon16),
    ("$reftext(en+TST+JON 1:13)", _jon13),                # another project
    ("$reftext(en+XYZ+JON 1:13)", "[ERROR: No project for en+XYZ]"),
    ("$reftext(MAT 1:1)", "[ERROR: No MAT in project FRA]"),
    ("$reftext(JON 1:99)", "[ERROR: Reference verse JON 1:99 out of range]"),
])
def test_reftext(tmp_path, s, res):
    projects = _projects(str(tmp_path))
    mod = Module(None, project=projects.find("FRA"), projects=projects)
    out = mod.expand(s)
    if out != res:
        fail(f"{s!r} gave {out!r}")

def test_reftext_noproject():
    assert _mod().expand("$reftext(JON 1:1)") == "[ERROR: No project to take scripture from]"

def _mref(tmp_path, src):
    """ Flattens src in the FRA project, returning the USFM, its root and the errors """
    projects = _projects(str(tmp_path))
    _project(str(tmp_path), "DOL", lang="en:::", booknames=False)
    with open(os.path.join(str(tmp_path), "DOL", "32JONDOL.usfm"), "w", encoding="utf-8") as outf:
        outf.write("\\id JON\n\\c 1\n\\p\n\\v 1 It cost $5 and $name.\n")
    projects.addProject("DOL", os.path.join(str(tmp_path), "DOL"))
    mod = Module(parseModule(src), project=projects.find("FRA"), projects=projects,
                 variables={"name": "Fred"})
    res = mod.flatten()
    return res.outUsfm(), res.getroot(), mod.errors

def _styles(root):
    return [e.get("style") for e in root.iter() if e.get("style")]

def test_mref(tmp_path):
    res, root, errors = _mref(tmp_path, "\\id FRT\n\\p Before\n\\mref|JON 1:13\\*\n\\p After\n")
    assert not errors
    assert "\\p Before\n" in res and "\\p After" in res
    assert "\\v 13 Nevertheless, the men rowed hard to get back to dry land" in res
    assert "\\f" not in res and "vid" not in res          # no notes, no getrefs \\vid
    assert "\\toc1" not in res and "\\h " not in res     # nor the book's headers

@pytest.mark.parametrize("conf, ref, has, hasnt", [
    ('verses="false" chapters="false"', "JON 1:17-2:2", [r"\s1 Jonahʼs Prayer", "From inside the fish"], [r"\v", r"\c"]),
    ('', "JON 1:13", [r"\v 13"], [r"\f"]),
    ('notes="f"', "JON 1:13", [r"\f + \fr 1:13"], []),
    ('notes="x"', "JON 1:13", [], [r"\f"]),
    ('notes="true"', "JON 1:13", [r"\f + \fr 1:13"], []),
    ('notes="false"', "JON 1:13", [], [r"\f"]),
    ('intro="true"', "JON 1:1", [r"\mt1 Jonah", r"\v 1"], [r"\toc1"]),
    ('', "JON 1:1", [r"\v 1"], [r"\mt1"]),
    ('', "JON 2", ["\\c 2\n", r"\v 10"], [r"\v 1 Now", r"\s1"]),
    ('headings="true"', "JON 2", ["\\c 2\n\\s1 Jonahʼs Prayer", r"\v 10"], []),
    ('chapters="false"', "JON 2", [r"\v 10"], [r"\c"]),
    # headings at the start of the fragment, not those inside it
    ('', "JON 1:3-4", [r"\v 3", r"\s1 The Great Storm"], []),
    ('', "JON 1:4", [r"\v 4"], [r"\s1", r"\r "]),
    ('headings="true"', "JON 1:4", [r"\s1 The Great Storm", r"\v 4"], []),
    ('headings="true"', "JON 2:1", [r"\s1 Jonahʼs Prayer", r"\v 1"], []),
    ('intro="true"', "JON 1:1-2", [r"\mt1 Jonah", r"\v 1"], [r"\s1"]),
    ('intro="true" headings="true"', "JON 1:1-2", [r"\mt1 Jonah", r"\s1 Jonah Flees"], []),
    # the intro comes once per book
    ('intro="true"', "JON 1:1; 2:1", [r"\mt1 Jonah", r"\v 1 From inside"], [r"\mt1 Jonah\n\\p \v 1 From"]),
])
def test_mref_config(tmp_path, conf, ref, has, hasnt):
    res, root, errors = _mref(tmp_path, f'\\id FRT\n\\mrefconfig|name="c" {conf}\\*\n\\p\n\\mref|ref="{ref}" config="c"\\*\n')
    assert not errors
    for h in has:
        if h not in res:
            fail(f"{h!r} not in {res}")
    for h in hasnt:
        if h in res:
            fail(f"{h!r} in {res}")

def test_mref_default(tmp_path):
    """ \\mrefconfig with no name changes the default """
    res, root, errors = _mref(tmp_path, '\\id FRT\n\\mrefconfig|notes="f"\\*\n\\p\n\\mref|JON 1:13\\*\n')
    assert r"\f + \fr 1:13" in res and not errors

def test_mref_nodollar(tmp_path):
    """ $ in the inserted scripture is not expanded, unlike in the module """
    res, root, errors = _mref(tmp_path, "\\id FRT\n\\p $name\n\\mref|en+DOL+JON 1:1\\*\n")
    assert "\\p Fred" in res and "It cost $5 and $name." in res and not errors

def test_mref_projects(tmp_path):
    """ The refs of a list can come from different projects. A product carries
        on to the following refs, and a bare + goes back to the module's project. """
    res, root, errors = _mref(tmp_path, '\\id FRT\n\\p\n\\mref|ref="JON 1:1; en+DOL+JON 1:1; +JON 1:2"\\*\n')
    assert not errors
    assert [v.get("number") for v in root.iter("verse")] == ["1", "1", "2"]
    assert "It cost" in res and "Get up!" in res

@pytest.mark.parametrize("src, err", [
    (r'\mref|ref=""\*', r'\mref has no ref'),
    (r'\mref|ref="JON 1:1" config="nothing"\*', r'No \mrefconfig nothing'),
    (r'\mrefconfig|name="x" colour="red"\*', r'Unknown \mrefconfig setting colour'),
    (r'\mref|JON 1:99\*', 'Reference verse JON 1:99 out of range'),
    (r'\mref|MAT 1:1\*', 'No MAT in project FRA'),
    (r'\mref|en+XYZ+JON 1:1\*', 'No project for en+XYZ'),
])
def test_mref_errors(tmp_path, src, err):
    res, root, errors = _mref(tmp_path, "\\id FRT\n\\p " + src + "\n")
    if len(errors) != 1 or not errors[0][0].startswith(err):
        fail(f"{src}: {errors}")

def test_flattenmodulefile_parseerrors(tmp_path):
    """ USFM parsing errors, such as a newline in an attribute, are reported """
    infile = tmp_path / "mod.usfm"
    infile.write_text('\\id FRT\n\\p\n\\mlet|var="x" val="$op(+,\n 1, 2)"\\*$x $s(JON 1:1, a, b)\n', encoding="utf-8")
    errors = []
    flattenModuleFile(str(infile), envs={"*": bkenv}, moderrors=errors)
    assert len(errors) == 2
    assert errors[0][0].startswith("Newlines not allowed in attributes") and errors[0][1] == 3
    assert errors[1][0].startswith("Wrong number of arguments (3) to $s")

def _write(path, s):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as outf:
        outf.write(s)

def _flatfile(path, **kw):
    errors = []
    res = flattenModuleFile(str(path), envs={"*": bkenv}, moderrors=errors, **kw)
    return res.outUsfm(), errors

def test_minclude(tmp_path):
    """ An included file's macros can be used before the include, and its own
        includes are relative to it """
    _write(tmp_path / "main.usfm", "\\id FRT\n\\p $hi(Fred)\n\\minclude|lib/fns.txt\\*\n\\p $bye\n")
    _write(tmp_path / "lib" / "fns.txt", "\\id FRT functions\n\\mdef-s|name=\"hi\" args=\"x\"\\*Hello $x\\mdef-e\\*\n"
                                          "\\minclude|more.txt\\*\n")
    _write(tmp_path / "lib" / "more.txt", "\\id FRT more\n\\mlet|var=\"bye\" val=\"Goodbye\"\\*\n\\p Included text\n")
    res, errors = _flatfile(tmp_path / "main.usfm")
    assert not errors
    assert "\\p Hello Fred\n" in res and "\\p Included text\n" in res and "\\p Goodbye" in res
    assert "\\id FRT functions" not in res and "minclude" not in res

def test_minclude_var(tmp_path):
    """ Processor defined variables can make the name """
    _write(tmp_path / "main.usfm", "\\id FRT\n\\minclude|$part.txt\\*\n")
    _write(tmp_path / "intro.txt", "\\id FRT\n\\p The intro\n")
    res, errors = _flatfile(tmp_path / "main.usfm", variables={"part": "intro"})
    assert "\\p The intro" in res and not errors

@pytest.mark.parametrize("files, err", [
    ({"main.usfm": "\\id FRT\n\\p \\minclude|nothing.txt\\*\n"}, "No file nothing.txt to include"),
    ({"main.usfm": "\\id FRT\n\\p \\minclude|main.usfm\\*\n"}, "main.usfm includes itself"),
    ({"main.usfm": "\\id FRT\n\\p \\minclude|a.txt\\*\n", "a.txt": "\\id FRT\n\\p \\minclude|main.usfm\\*\n"},
        "main.usfm includes itself"),
    ({"main.usfm": "\\id FRT\n\\p \\minclude|a.txt\\*\n", "a.txt": "\\id FRT\n\\p \\w x|a=\"b\nc\"\\w*\n"},
        "Newlines not allowed in attributes"),
])
def test_minclude_errors(tmp_path, files, err):
    for k, v in files.items():
        _write(tmp_path / k, v)
    res, errors = _flatfile(tmp_path / "main.usfm")
    if len(errors) != 1 or not errors[0][0].startswith(err):
        fail(f"{files}: {errors}")

_ldmldir = os.path.join(os.path.dirname(__file__), "ldml")
_cal = 'dates/calendars/calendar[@type="gregorian"]/'

@pytest.mark.parametrize("s, res", [
    ("$ldml(" + _cal + 'days/dayContext[@type="format"]/dayWidth[@type="wide"]/day[@type="sun"])', "Sunday"),
    # whitespace is removed from the path, except in quotes
    ("$ldml(" + _cal + 'days/dayContext\n  [@type="stand-alone"]/dayWidth[@type="abbreviated"]/day[@type="wed"])', "Wed"),
    ("$ldml(" + _cal + 'months/monthContext[@type="stand-alone"]/monthWidth[@type="wide"]/month[@type="12"], en)', "December"),
    ("$ldml(dates/nothing)", "[ERROR: Nothing at dates/nothing in the LDML for en]"),
    ("$ldml(dates[@x)", "[ERROR: Bad LDML path dates[@x]"),
    ("$ldml(dates, ../en)", "[ERROR: Can't get the LDML for ../en: Bad language tag '../en']"),
])
def test_ldml(s, res):
    mod = Module(None, envs={"*": bkenv}, lang="en", ldmldir=_ldmldir)
    out = mod.expand(s)
    if out != res:
        fail(f"{s!r} gave {out!r}")

def test_ldml_nolang():
    mod = Module(None, envs={"*": bkenv}, ldmldir=_ldmldir)
    assert mod.expand("$ldml(dates)") == "[ERROR: No language for $ldml]"
    mod = Module(None, envs={"*": bkenv}, variables={"LANG": "en"}, ldmldir=_ldmldir)
    assert mod.expand("$ldml(" + _cal + 'months/monthContext[@type="format"]/monthWidth[@type="abbreviated"]/month[@type="2"])') == "Feb"

def test_ldml_fetch(tmp_path):
    """ A missing file is fetched and cached; refresh fetches it again, once """
    with open(os.path.join(_ldmldir, "en.xml"), "rb") as inf:
        data = inf.read()
    fetches = []
    def fetch(lang):
        fetches.append(lang)
        return data
    s = "$ldml(" + _cal + 'days/dayContext[@type="format"]/dayWidth[@type="wide"]/day[@type="mon"])'
    for refresh, res in ((False, ["en"]), (False, ["en"]), (True, ["en", "en"])):
        mod = Module(None, envs={"*": bkenv}, lang="en", ldmldir=str(tmp_path), ldmlfetch=fetch, refreshldml=refresh)
        assert mod.expand(s) == "Monday" and mod.expand(s) == "Monday"
        assert fetches == res and os.path.exists(tmp_path / "en.xml")

def test_ldml_baddata(tmp_path):
    mod = Module(None, envs={"*": bkenv}, lang="en", ldmldir=str(tmp_path), ldmlfetch=lambda l: b"<html>oops")
    assert mod.expand("$ldml(dates)").startswith("[ERROR: Can't get the LDML for en: Bad LDML for en")
    assert not os.path.exists(tmp_path / "en.xml")

def test_ldml_cachedir(monkeypatch):
    from usfmtc.ldml import cachedir
    monkeypatch.setenv("USFMTC_CACHE", "/somewhere")
    assert cachedir() == os.path.join("/somewhere", "ldml")
    if os.sys.platform not in ("win32", "darwin"):
        monkeypatch.delenv("USFMTC_CACHE")
        monkeypatch.setenv("XDG_CACHE_HOME", "/xdg")
        assert cachedir() == os.path.join("/xdg", "usfmtc", "ldml")

def test_gather_prune():
    """ Gathering removes what it leaves empty, but not what was empty already,
        nor milestones """
    res, v = _vars(r"""\id GEN module test
\c 1
\p
\v 1 Text
\b
\mdef-s|name="row" args="x"\*
\tr \tc1 $x
\mdef-e\*
\p $row(a)
""")
    assert "\\b \n" in res                  # the author's empty \\b stays
    assert "\\tr \\tc1 a" in res and res.count("\\tr") == 1
    assert "\\tr \n" not in res and "\\tr\n" not in res

def test_calendar(tmp_path):
    """ The calendar example from the spec, with readings from Jonah """
    projects = _projects(str(tmp_path))
    errors = []
    res = flattenModuleFile(os.path.join(os.path.dirname(__file__), "calendar", "calendar.usfm"),
                            project=projects.find("FRA"), projects=projects, lang="en",
                            booknames=os.path.join(os.path.dirname(__file__), "BookNames.xml"),
                            ldmldir=_ldmldir, moderrors=errors)
    out = res.outUsfm()
    root = res.getroot()
    assert not errors, errors
    assert "$" not in out
    assert "\\mt1 Scripture Calendar" in out and "\\s January 2027" in out
    rows = list(root.iter("row"))
    assert [c.text.strip() for c in rows[0]] == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    assert len(rows) == 6 and all(len(r) == 7 for r in rows)
    days = [[c.find("char").text if c.find("char") is not None else None for c in r] for r in rows[1:]]
    assert days[0] == ["31", None, None, None, None, "1", "2"]      # 1 Jan 2027 is a Friday
    assert days[4] == ["24", "25", "26", "27", "28", "29", "30"]
    cells = {c.find("char").text: c for r in rows[1:] for c in r if c.find("char") is not None}
    assert "Now the word of the LORD came to Jonah son of Amittai" in "".join(cells["1"].itertext())
    assert "Jonah 1:1" in "".join(cells["1"].itertext())
    assert "Jonah 1:10" in "".join(cells["10"].itertext())
    assert "Jonah 3:1" in "".join(cells["11"].itertext())
    assert "Jonah 4:11" in "".join(cells["31"].itertext())

_jon117 = ("Now the LORD had appointed a great fish to swallow Jonah, and Jonah spent three days "
           "and three nights in the belly of the fish.")

@pytest.mark.parametrize("s, res", [
    ("$len($rall(JON 1, v)) $r(JON 1, last.last)", "17 JON 1:17"),        # $VRS defaults to eng
    ("\\mlet|var=\"VRS\" val=\"org\"\\*$len($rall(JON 1, v)) $r(JON 1, last.last)", "16 JON 1:16"),
    ("\\mlet|var=\"VRS\" val=\"eng\"\\*$reftext(JON 1:17)", _jon117),
    ("\\mlet|var=\"VRS\" val=\"org\"\\*$reftext(JON 2:1)", _jon117),           # eng 1:17 is org 2:1
    ("\\mlet|var=\"VRS\" val=\"nothing\"\\*$reftext(JON 2:1)", "[ERROR: Unknown versification nothing]"),
])
def test_vrs(tmp_path, s, res):
    out, root, errors = _mref(tmp_path, "\\id FRT\n\\p " + s + "\n")
    assert out.split("\\p ", 1)[1].strip() == res

@pytest.mark.parametrize("ref, verses", [
    ("JON 2:1", [("c", "2"), ("v", "1")]),                  # eng 1:17, which starts org 2
    ("JON 1:16-2:2", [("v", "16"), ("c", "2"), ("v", "1"), ("v", "2")]),
    ("JON 2:10-11", [("v", "10"), ("v", "11")]),           # eng 2:9-10
    ("JON 3:1-2", [("c", "3"), ("v", "1"), ("v", "2")]),    # the same in both
])
def test_vrs_mref(tmp_path, ref, verses):
    """ \\mref finds the scripture in the project's versification (eng) and gives
        it in the module's (org) """
    out, root, errors = _mref(tmp_path, f'\\id FRT\n\\mlet|var="VRS" val="org"\\*\n\\p\n\\mref|{ref}\\*\n')
    assert not errors
    got = [(e.tag[0], e.get("number")) for e in root.iter() if e.tag in ("chapter", "verse")]
    assert got == verses, out
    if ref == "JON 2:1":
        assert _jon117 in out

def test_vrs_file(tmp_path):
    """ $VRS can name a .vrs file beside the module """
    import shutil, usfmtc.versification
    shutil.copy(os.path.join(os.path.dirname(usfmtc.versification.__file__), "org.vrs"), tmp_path / "my.vrs")
    _write(tmp_path / "main.usfm", '\\id FRT\n\\mlet|var="VRS" val="my.vrs"\\*\n\\p $len($rall(JON 1, v))\n')
    res, errors = _flatfile(tmp_path / "main.usfm")
    assert "\\p 16" in res and not errors

def test_vrs_project(tmp_path):
    """ Without $VRS, the module's versification is its project's """
    from usfmtc.projects import Projects
    _project(str(tmp_path), "ORG", Versification="1")
    projects = Projects(str(tmp_path))
    mod = Module(None, project=projects.find("ORG"), projects=projects)
    assert mod.expand("$len($rall(JON 1, v)) $r(JON 1, last.last)") == "16 JON 1:16"
    assert mod._vrs() is projects.find("ORG").settings.getVersification()
    assert Module(None, envs={"*": bkenv}).expand("$len($rall(JON 1, v))") == "17"     # no project: eng
