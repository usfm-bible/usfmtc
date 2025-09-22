import pytest
from pytest import fail
import usfmtc
from usfmtc.usxmodel import etCmp
import xml.etree.ElementTree as et
import re, json

def _dousfm(s, grammar=None, errors=False, version=None):
    doc = usfmtc.readFile(s, informat="usfm", grammar=grammar)
    doc.canonicalise()
    doc.version = version or "3.1"
    r = doc.getroot()
    et.dump(r)
    if doc.errors is not None and len(doc.errors):
        print("\nParser Errors:\n")
        print("\n".join(["{0} at {2} pos {1}".format(*e) for e in doc.errors]))
        if not errors:
            fail("Unexpected parser errors encountered")
    j = doc.outUsj(None)
    js = json.dumps(j, indent=2, ensure_ascii=False)
    tj = usfmtc.readFile(js, informat="usj", grammar=grammar)
    if not etCmp(r, tj.getroot(), verbose=True):
        print(j)
        breakpoint()
        fail(f"USJ did not round trip")
    f = doc.outUsfm(None)
    print(f)
    return (doc, f)

def test_hardspaces():
    usfm = r"""\id TST testing hardspaces
\c 1 \p \v 1 This{0}has a hard{0}space\f + \fr 1:1{0}\ft And here\f*""".format("\u00A0")
    doc, f = _dousfm(usfm)
    r = doc.getroot()
    e = r.find('.//char[@style="fr"]')
    t = e.text
    if not t.endswith("\u00A0"):
        fail("No hard space after fr in usx")
    if not re.search("\u00A0\\\\ft", f):
        fail("No hard space after fr in usfm")

def test_glossary():
    usfm = r"""\id TST glossary in text
\c 1 \p \v 1 We have \w glossary\w* words to deal with"""
    doc, f = _dousfm(usfm)
    if not re.search(" \\w", f):
        fail("No space before glossary word in {f}")

def test_chap():
    usfm = r"""\id TST chapters followed by space
\c 3\p^97 \v 1 This is tight"""
    doc, f = _dousfm(usfm)
    if not re.search(r" 3\s", f, flags=re.S):
        fail("No space after chapter number in {f}")

def test_vp():
    usfm = r"""\id TST publishable verses
\c 3
\cp 3a\cp*
\p
\v 1 \vp (23)\vp* This is the text"""
    doc, f = _dousfm(usfm)
    if 'vp*' not in f:
        fail("vp not closed in {f}")
    if 'cp*' in f:
        fail("Found cp* in {f}")

def test_headms():
    grammar = usfmtc.usfmparser.Grammar()
    grammar.marker_categories['zlabel'] = 'milestone'
    grammar.attribmap['zlabel'] = 'id'
    usfm = r"""\id GEN A test
\zlabel|GEN\*
\h Genesis
\toc1 Genesis
\c 1
\p
\v 1 In the beginning God"""
    doc, f = _dousfm(usfm, grammar=grammar)
    if "\n\\zlabel" not in f:
        fail("zlabel escaped in {f}")

def test_standalone():
    grammar = usfmtc.usfmparser.Grammar()
    grammar.marker_categories['zlabel'] = 'standalone'
    usfm = r"""\id GEN A test
\h Genesis
\toc1 Genesis
\c 1
\p
\v 1 In the beginning \zlabel God"""
    doc, f = _dousfm(usfm, grammar=grammar)
    if "beginning \\zlabel God" not in f:
        fail(f"zlabel escaped in {f}")

def test_charattrib():
    usfm = r"""\id LUK A test
\c 1
\p \v 1 \+w Why|strong="G5101"\+w*  \+w were|strong="G1510"\+w* \+w you|strong="G3754"\+w* \+w looking|strong="G2212"\+w* \+w for|strong="G3754"\+w* \+w me|strong="G3004"\+w*? \+w Didn’t|strong="G3756"\+w* \+w you|strong="G3754"\+w*"""
    doc, f = _dousfm(usfm)
    if len(doc.getroot()[2]) != 9:
        fail(f"{len(doc.getroot()[2])} {f}")

def test_closext():
    grammar = usfmtc.Grammar()
    grammar.marker_categories['wl']="char"
    usfm = r"""\id XXS A test
\li \bd 5601\bd* \wg Ὠβήδ\wg* \wl Ōbḗd\wl* \k వోబెద-\k*; a person in the genealogy of Jesus; \xt $a(MAT 1:5)\xt*"""
    doc, f = _dousfm(usfm, grammar=grammar)
    if 'xt*' not in f:
        fail(f"{f}")

def test_verse_spacing():
    usfm = r"""\id ROM Myanmar literal Bible
\c 1
\p
\v 1 လူဇာတိအားဖြင်း ဒါဝိဒ်အမျိုးဖြစ်တော်မူ ထသော၊ \v 2 သေခြင်းမှထမြောက်တော်မူ၍၊
\v 3 သန့်ရှင်းသောဝိညာဉ်အားဖြင့်၊
\v 4 တန်ခိုးနှင့်တကွ ဘုရားသခင်၏သားတော်"""
    doc, f = _dousfm(usfm)
    if re.search(r"[^ \n\t]\\v", f):
        fail(f"{f}: no space before \\v")

def test_cellrange():
    usfm = r"""\id 1CH table test
\c 1
\p
\tr
\tc1 \v 1 This\tc2 explains everything
\tr
\tc1-2 along with\tc3 this information."""
    doc, f = _dousfm(usfm)
    if doc.getroot()[3][1][0].get("colspan", "") != "2":
        fail(f"{f}: no tc1-2")

def test_msqt():
    usfm = r"""\id JUD paired ms
\c 1
\pc \qt-s|OnCross\*{O Isus anθar o Nazaret, //o Thagar le Judeenqo.} \qt-e \*"""
    doc, f = _dousfm(usfm)
    if doc.getroot()[2][0].tag != "ms":
        fail(f"{f}: not a milestone")

def test_footnote3():
    usfm = r"""\id PHM footnote structure
\c 1
\p
\v 1 This is a test\f + \fr 1:1 \ft And a note in it for \xt John 3:16|href="JHN 3:16"\xt*\f*
"""
    doc, f = _dousfm(usfm)
    if "fr*" in f:
        fail(f"{f}: bad structure")
    if 'xt*' not in f or 'ref' in f:        # is this what we really want?
        fail(f"{f}: bad ref handling")

def test_va():
    usfm = r"""\id GEN hanging vas
\c 32
\p \v 10-12 \va 12 \va* This is verse twelve and all it's interesting text
\p
\va 10 \va* Now verse 10 followed by \va 11 \va* verse 11. Done.
"""
    doc, f = _dousfm(usfm, errors=True)
    if doc.errors is not None and len(doc.errors) != 3 or doc.errors[0][1].l != 4:
        print(doc.errors)
        fail(f"Wrong number of errors")

def test_footnote4():
    usfm = r"""\id PHM footnote structure
\c 1
\p
\v 1 This is a test\f + \fr 1:1 \ft And a note in the \+fq test\+fq* for \xt John 3:16|href="JHN 3:16"\xt*\f*
"""
    doc, f = _dousfm(usfm)
    if r"\fq test \ft " not in f:
        fail(f"nested fq not converted")

def test_unknown():
    usfm = r"""\id MRK test unknown marker
\c 1
\pqr
\v 1 This is a test
"""
    doc, f = _dousfm(usfm, errors=True)
    if doc.errors is None or len(doc.errors) != 1 or doc.errors[0][1].l != 2:
        print(doc.errors)
        fail(f"Bad handling of \\pqr")

def test_attribs32():
    usfm = r"""\id MRK test 3.2 attributes
\usfm 3.2
\c 1
\p
\v 1 This is a test\f|category="fred"| + \fr 1:1 \ft Fred was a dog\f* of attributes
"""
    doc, f = _dousfm(usfm, version="3.1")
    if r"\cat fred" not in f:
        fail(f"Can't parse front attributes: {f}")

def test_vp():
    usfm = r"""\id MRK test versepub
\usfm 3.1
\c 1
\p
\v 1 \vp A\vp* This is a test
"""
    doc, f = _dousfm(usfm, version="3.2")
    if "vp" in f:
        fail(f"Bad vp in {f}")
    doc, f = _dousfm(usfm, version="3.1")
    if "number" in f:
        fail(f"Bad pubnumber in {f}")

def test_badverse():
    usfm = r"""\id MAT bad verse
\c 1
\p
\v Here is the genealogy
"""
    doc, f = _dousfm(usfm, errors=True)

def test_periph():
    usfm = r"""\id FRT testing periph
\periph Title Page|id="title"
\p This is a test
"""
    doc, f = _dousfm(usfm)
    if not doc.getroot()[1].get("id", None):
        fail(f"Bad periph {f}")

def test_ver31():
    usfm = r"""\id MAT or somewhere
\p Some text
"""
    doc, f = _dousfm(usfm)
    if 'usfm' not in f:
        fail(f"Missing usfm header in {f}")

def test_regularise():
    usfm = r"""\id MRK
\c 1
\p \v 1 This is a verse\v 2 this is one too
"""
    doc, f = _dousfm(usfm)
    doc.regularise()
    if not doc.getroot()[2][0].tail.endswith(" "):
        fail(f"Missing inserted space before v2 in {f}")

