import pytest
from pytest import fail
from usfmtc import readFile
from usfmtc.module import Module
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
