import pytest
from pytest import fail
from usfmtc import readFile
from usfmtc.module import Module, ModuleFatalError
from usfmtc.reference import BookNamesEnvironment
import os

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
    doc = readFile(usfm, informat="usfm")
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
    mod = _mod(readFile(usfm, informat="usfm"))
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
    mod = _mod(readFile(usfm, informat="usfm"))
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
    doc = readFile(r"""\id GEN module test
\c 1
\p
\v 1 \mlet-s|var="x"\*$who and $name\mlet-e\*
""", informat="usfm")
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
    doc = readFile(r"""\id GEN module test
\c 1
\p
\v 1 \mlet-s|var="x"\*\mlet|var="n" val="$n$n"\*\mlet|var="m" val="M"\*\mlet-e\*
""", informat="usfm")
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
    """ A block between paragraphs adds paragraphs. The empty paragraph left by
        what followed \\mfor-e is harmless """
    res, v = _vars("\\id GEN module test\n\\c 1\n\\mfor-s|var=\"x\" list=\"a\x1cb\"\\*\n"
r"""\p $x \bd y\bd*
\mfor-e\*
\p after
""")
    if "\\c 1\n\\p a \\bd y\\bd*\n\\p b \\bd y\\bd*\n\\p \n\\p after" not in res:
        fail(f"Bad output {res}")

def _forlist(lst, attrs, body="$x;"):
    """ Flattens an \\mfor over the list lst, returning the output of verse 1 """
    usfm = ("\\id GEN module test\n\\c 1\n\\p\n\\v 1 \\mfor-s|var=\"x\" list=\"" + lst + "\""
            + attrs + "\\*" + body + "\\mfor-e\\*\n")
    mod = _mod(readFile(usfm, informat="usfm"))
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
    doc = readFile("\\id GEN module test\n\\c 1\n\\p\n\\v 1 \\mfor-s|var=\"x\" list=\"one\x1e1\x1ctwo\x1e2\"\\*"
                   "\\mlet|var=\"last\" val=\"$x\"\\*\\mfor-e\\*\n", informat="usfm")
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
        The rest of the \\li holding \\mfor-e is an empty paragraph, which is harmless """
    res, v = _vars(_mdoc("\\mlet|var=\"xs\" val=\"a\x1cb\"\\*\n" + r"""\mdef-s|name="items" args="pre"\*
\mfor-s|var="x" list="$xs"\*
\li $pre $x\mfor-e\*
\mdef-e\*
\c 1
\p
\v 1 \mlet|var="out" val="$items(-)"\*
"""))
    if v["out"] != "\\li - a\n\\li - b\n\\li":
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
    mod = _mod(readFile(_mdoc(r"""\c 1
\p
\v 1 \mfor-s|var="x" list="a"\*\mdef-s|name="m" args=""\*one\mdef-e\*\mfor-e\*
"""), informat="usfm"))
    res = mod.flatten().outUsfm(None)
    if len(mod.errors) != 1 or not mod.errors[0][0].startswith("\\mdef-s must be at the top level") \
            or "one" in res:
        fail(f"Errors {mod.errors} in {res}")

def test_mdef_recursion():
    mod = _mod(readFile(_mdoc(r"""\mdef-s|name="loop" args="x"\*$loop($x)\mdef-e\*
\c 1
\p
\v 1 $loop(a)
"""), informat="usfm"))
    with pytest.raises(ModuleFatalError):
        mod.flatten()

def _errors(usfm):
    mod = _mod(readFile(usfm, informat="usfm"))
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
    mod = _mod(readFile(usfm, informat="usfm"))
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
    mod = Module(readFile(_heads + "\\p\n\\v 1 $s($bs) $b(y)\n", informat="usfm"),
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
