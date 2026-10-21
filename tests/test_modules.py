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
