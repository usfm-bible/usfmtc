import pytest
from pytest import fail
import usfmtc
from usfmtc.usxmodel import etCmp
from usfmtc.usfmparser import Grammar
import xml.etree.ElementTree as et
import re, json

def _dousfm(s, grammar=None, errors=False, version=None, nofail=False, **kw):
    doc = usfmtc.readFile(s, informat="usfm", grammar=grammar)
    doc.canonicalise(version=version)
    doc.version = version or "3.1"
    r = doc.getroot()
    et.dump(r)
    if doc.errors is not None and len(doc.errors):
        print("\nParser Errors:\n")
        print("\n".join(["{0} at {2} pos {1}".format(*e) for e in doc.errors]))
        if not errors and not nofail:
            fail("Unexpected parser errors encountered")
    j = doc.outUsj(None)
    js = json.dumps(j, indent=2, ensure_ascii=False)
    tj = usfmtc.readFile(js, informat="usj", grammar=grammar)
    if not etCmp(r, tj.getroot(), verbose=True):
        print(j)
        if not nofail:
            fail(f"USJ did not round trip")
    f = doc.outUsfm(None, **kw)
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
    if not re.search("~\\\\ft", f):
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
    grammar = Grammar()
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
\tc2-3 along with\tc4 this information."""
    doc, f = _dousfm(usfm)
    if doc.getroot()[3][1][0].get("colspan", "") != "2":
        fail(f"{f}: no tc2-3")

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
    doc, f = _dousfm(usfm, version="3.0")
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
    try:
        doc, f = _dousfm(usfm, errors=True)
    except SyntaxError:
        return
    ve = doc.getroot().find(".//verse")
    v = ve.get("number", "")
    if v != "Here":
        fail(f"Bad verse parsed in {usfm}")

def test_periph():
    usfm = r"""\id FRT testing periph
\periph Title Page|id="title"
\p This is a test
"""
    doc, f = _dousfm(usfm)
    if not doc.getroot()[1].get("id", None):
        fail(f"Bad periph {f}")

def test_periph2():
    source = r"""\id FRT
\usfm 3.1
\periph Introduction|id="introduction"
\p Text.
"""
    doc, f = _dousfm(source)
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

def test_canonicalxt():
    usfm = r"""\id JHN SLU
\c 6
\p
\v 53 Lemadendye Yesuske tyanuk ti sir ma byohe, \wj “Nam kutanuk ti e ne mlay: kolnye ei neke lema mi Irkye Ananke tenanke,\wj*\f + \fr 6:53 \ft Ti ayat ne Yesuske byohe, \fq Irkye Ananke\fq*, neke Yesuske yal ma lyosu I a myesan bo. Kola ne ti ayat \xt 6:27\xt*ke ode \xt 6:62\xt*ke dakun. (Matos ti \xt Dan. 7:13-14\xt*.)\f* \wj ode lema myenw a larake, desikeo ana mormyorif manal nini namke lema kimin a e.\wj*
\v 54 \wj Klala esei desike nya tenakkwe ode yenw a larakkwe, desikeo i desike mormyorif manal nini namke kimin a i ti kiba knaru ne, ode ana kaorif a i ti sew a nuske ktem ne ana kilodur ne.\wj*
"""
    doc, f = _dousfm(usfm)
    if len(doc.getroot()[2][2]) != 4 or len(doc.getroot()[2][2][3]) != 3:
        fail(f"Bad footnote canonicalising in {f}")

def test_specialchars():
    usfm = r"""\id JHN test
\c 4
\p
\v 1 This tests \| pipe, \~ tilde and \\ backslash. Notice the hard~space
"""
    print(usfm)
    doc, f = _dousfm(usfm)
    if '\\\\\\' in f or '~' not in f:
        fail(f"Bad character escaping in {f}")

def test_attribescapes():
    """ Escaped characters in attribute values read and write back unchanged """
    usfm = r"""\id JHN attribute escapes
\c 1
\p
\v 1 \w word|lemma="a\"b\\c\|d"\w*
"""
    doc, f = _dousfm(usfm)
    for d in (doc, usfmtc.readFile(f, informat="usfm")):
        lemma = [e.get("lemma") for e in d.getroot().iter() if e.tag == "char"]
        if lemma != ['a"b\\c|d']:
            fail(f"lemma is {lemma} in {f}")

def test_emptyattrib():
    usfm = r"""\id JHN empty attributes
\p
\v 1 \rb normal|good\rb* \rb test|\rb* \rb |empty\rb*
"""
    doc, f = _dousfm(usfm)
    if 'test' not in f or 'empty' not in f:
        fail(f"{f} is missing data")

def test_tilde():
    usfm = r"""\id JHN with tildes
\p
\v 1 This is a~test
"""
    doc, f = _dousfm(usfm)
    if "~" not in f or "\u00A0" not in doc.getroot()[1][0].tail:
        fail(f"{f} has bad hard space")

def test_notilde():
    usfm = r"""\id JHN with tilde in footnote
\p
\v 1 This is a test\f + \fr 1:1~\ft No tildes here\f*
"""
    doc, f = _dousfm(usfm, notilde=True)
    if '~' in f:
        fail(f"{f} should have a hard space not tilde")

# @pytest.mark.skip
def test_unknowns():
    usfm = r"""\id MAT EN_ULT with alignment

\usfm 3.1
\c 1
\p \v 1 \zaln-s|x-strong="G09760" x-lemma="βίβλος" x-morph="Gr,N,,,,,NFS," x-occurrence="1" x-occurrences="1" x-content="βίβλος"\*\w The|x-occurrence="1" x-occurrences="1"\w* \w book|x-occurrence="1" x-occurrences="1"\w*\zaln-e\*
\zaln-s|x-strong="G10780" x-lemma="γένεσις" x-morph="Gr,N,,,,,GFS," x-occurrence="1" x-occurrences="1" x-content="γενέσεως"\*\w of|x-occurrence="1" x-occurrences="4"\w* \w the|x-occurrence="1" x-occurrences="1"\w* \w genealogy|x-occurrence="1" x-occurrences="1"\w*\zaln-e\*
\badchar testing|parms="test"\badchar*
"""

    doc, f = _dousfm(usfm, nofail=True)
    if f != usfm:
        fail(f"{f} is not like the original")

def test_error1():
    usfm = r"""\id MAT test bad args
\usfm 3.1
\c 1
\p
\v 1 \vp 1/2\vp* This is a test
"""
    doc, f = _dousfm(usfm, nofail=True)

def test_vid():
    usfm = r"""\id LUK test
\usfm 3.1
\vid|LUK 4:17\*
\p
\v 17 This is a test
"""
    doc, f = _dousfm(usfm, nofail=True)
    if 'vid' not in f:
        fail(f"vid lost in round tripping:\n{f}")

def test_preprocess():
    doc = usfmtc.readFile("\\id GEN\n\\p Hello X\n", informat="usfm", preprocess=lambda s: s.replace("X", "World"))
    assert "Hello World" in doc.outUsfm()

def test_attrib_newline():
    """ A newline in an attribute is an error, kept unless strict """
    s = '\\id GEN\n\\p \\w word|lemma="a\nb"\\w*\n'
    doc = usfmtc.readFile(s, informat="usfm")
    assert any("Newlines not allowed" in e[0] for e in doc.errors)
    with pytest.raises(SyntaxError, match="Newlines not allowed"):
        usfmtc.readFile(s, informat="usfm", strict=True)

def test_jsonround():
    usfm = r'''\id GEN
\c 1
\p
\v 1 See \ref Ps. 33:9|loc="PSA 33:9"\ref* and \jmp Glossary|href="#glossary"\jmp* here.
'''
    doc, f = _dousfm(usfm)
    usj = doc.saveAs(None, outformat="usj")
    usjt = json.dumps(usj)
    print(usjt)
    doc2 = usfmtc.readFile(usjt, informat="usj")
    res = doc2.saveAs(None, outformat="usfm")
    if "|Ps." in res:
        fail(f"Fronted attributes, since used {doc2.version}")

def test_unknown_marked():
    usfm = r"""\id GEN
\c 1
\p
\v 1 Hello \foo world\foo* and \bar there
"""
    doc, f = _dousfm(usfm, errors=True)
    unknowns = [e.get("style") for e in doc.getroot().iter() if getattr(e, "unknown", False)]
    assert unknowns == ["foo", "bar"]
    copied = [e.get("style") for e in doc.getroot().copy(deep=True).iter() if getattr(e, "unknown", False)]
    assert copied == ["foo", "bar"]
    assert "unknown" not in json.dumps(doc.outUsj(None)) and "unknown" not in doc.outUsx(None)
    assert r"\foo world\foo*" in f and r"\bar there" in f

def _unknowntree(usfm):
    doc, f = _dousfm(usfm, nofail=True)
    para = [e for e in doc.getroot() if e.tag == "para"][0]
    return para, f

def test_unknown_bare_stands_alone():
    """ A bare unknown marker doesn't take in the text and markers after it """
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p a \\zfoo b \\zbar c\n"
    para, f = _unknowntree(usfm)
    assert [(e.tag, e.get("style"), len(e), e.text) for e in para] == \
        [("ms", "zfoo", 0, None), ("ms", "zbar", 0, None)]
    assert f == usfm

def test_unknown_bare_keeps_space():
    """ The space between a bare unknown marker and its following text is kept """
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\pc \\zcopyright\n\\pc \\polyglotcolumn L\n"
    para, f = _unknowntree(usfm)
    assert [l.rstrip() for l in f.splitlines()] == usfm.splitlines()     # (a protective space may end a line)

def test_unknown_milestone_default_attrib():
    """ The bare attribute of an unknown milestone is written back bare """
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p a \\zglot|R\\* b\n"
    para, f = _unknowntree(usfm)
    assert para[0].tag == "ms" and para[0].get("style") == "zglot"
    assert f == usfm

def test_unknown_char_with_nested_char():
    """ An unknown char style still holds its content when a marker comes inside it """
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p a \\zfoo x \\bd y\\bd* z\\zfoo* b\n"
    para, f = _unknowntree(usfm)
    assert len(para) == 1 and para[0].tag == "char" and para[0].get("style") == "zfoo"
    assert para[0][0].get("style") == "bd"
    assert f == usfm

def test_unknown_char_attribs_after_text():
    """ Attributes after the text of an unknown char style stay with it, not the paragraph """
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p a \\zfoo text|x=\"1\"\\zfoo* b\n"
    para, f = _unknowntree(usfm)
    assert para.get("x") is None
    assert para[0].tag == "char" and para[0].get("x") == "1" and para[0].text == "text"
    assert f == usfm

def test_unknown_char_default_attrib_after_text():
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p a \\zfoo text|R\\zfoo* b\n"
    para, f = _unknowntree(usfm)
    assert para[0].tag == "char" and para[0].get("_unknown_") == "R"
    assert f == usfm

def test_standalone_given_attribs():
    """ A standalone marker given attributes and \\* becomes a milestone holding them """
    g = Grammar()
    g.marker_categories["zst"] = "standalone"
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p a \\zst|R\\* b\n"
    doc, f = _dousfm(usfm, grammar=g)        # no parser errors
    para = [e for e in doc.getroot() if e.tag == "para"][0]
    assert para.get("_unknown_") is None
    assert para[0].tag == "ms" and para[0].get("_unknown_") == "R" and para[0].get("x-bare") is None
    assert f == usfm

def test_unknown_after_bare_names_real_parent():
    """ A bare unknown marker contains nothing, so the next unknown is reported in the paragraph """
    doc = usfmtc.readFile("\\id GEN test\n\\p a \\zfoo \\zbar b\n", informat="usfm")
    msgs = [e[0] for e in doc.errors]
    assert msgs == ["Unknown tag 'zfoo' in 'p'", "Unknown tag 'zbar' in 'p'"]

def test_para_after_milestone_starts_line():
    """ A paragraph after a milestone between paragraphs starts on its own line """
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\periph Title|title\n\\zfoo\\*\n\\mt1 Title\n"
    doc, f = _dousfm(usfm, nofail=True)
    assert "\\zfoo\\*\n\\mt1 Title" in f

def test_space_after_milestone_at_para_start():
    """ The space after a milestone at the start of a paragraph is part of the text """
    g = Grammar()
    g.marker_categories["zvar"] = "milestone"
    usfm = "\\id GEN test\n\n\\usfm 3.1\n\\p \\zvar|lang\\* (\\zvar|iso\\*)\n"
    doc, f = _dousfm(usfm, grammar=g)
    assert f == usfm

def test_periph_title_kept():
    """ Text after a marker in a periph doesn't replace the periph's title """
    usfm = "\\id FRT test\n\n\\usfm 3.1\n\\periph First Page|firstpage\n\\zreset 1\n\\ip Text\n"
    doc, f = _dousfm(usfm, nofail=True)
    periph = [e for e in doc.getroot() if e.tag == "periph"][0]
    assert periph.get("alt") == "First Page"
    assert "\\zreset 1" in f

def test_standalone_attribs_between_paras():
    """ A standalone marker given attributes between paragraphs keeps them, even empty ones """
    g = Grammar()
    g.marker_categories["zst"] = "standalone"
    usfm = "\\id FRT test\n\n\\usfm 3.1\n\\periph Title|title\n\\p a\n\\zst|R\\*\n\\p b\n\\zst|\\*\n\\p c\n"
    doc, f = _dousfm(usfm, grammar=g)        # no parser errors
    assert "\\zst|R\\*" in f and "\\zst|\\*" in f

def test_attribs_with_nothing_to_belong_to():
    """ Attributes no element takes, and no unknown char style claims, are reported and kept """
    doc = usfmtc.readFile("\\id GEN test\n\\p a|x=\"1\" b\n\\p c\n", informat="usfm")
    assert any("nothing to belong to" in e[0] for e in doc.errors)
    paras = [e for e in doc.getroot() if e.tag == "para"]
    assert paras[0].get("x") == "1" and paras[1].get("x") is None

def test_remline():
    """ With remline, markup in a \\rem is just text, whatever the USFM version """
    usfm = "\\id GEN test\n\\usfm 3.1\n\\rem old: \\zccimg by-nd|size=\"col\"\\* and \\fig* here | x\n\\p text\n"
    doc = usfmtc.readFile(usfm, informat="usfm", remline=True)
    assert not doc.errors
    rem = [e for e in doc.getroot() if e.get("style") == "rem"][0]
    assert rem.text.strip() == "old: \\zccimg by-nd|size=\"col\"\\* and \\fig* here | x" and not len(rem)
    f = doc.outUsfm(None)
    assert "\\rem old: \\zccimg by-nd|size=\"col\"\\* and \\fig* here | x\n" in f
    doc = usfmtc.readFile(usfm, informat="usfm")        # without it, the markup is parsed
    assert doc.errors

def test_rem_written_literally():
    """ A \\rem line is written back as it was, markup and all (USFM 3.2) """
    usfm = "\\id GEN test\n\n\\usfm 3.2\n\\rem old: \\zfoo|x\\* and \\fig* here | x\n\\p text\n"
    doc = usfmtc.readFile(usfm, informat="usfm")
    assert not doc.errors
    assert "\\rem old: \\zfoo|x\\* and \\fig* here | x\n" in doc.outUsfm(None)

def test_char_escapes():
    """ USFM 3.2 character escapes in the text; \\u0000 and malformed ones give a space """
    usfm = ("\\id GEN test\n\\usfm 3.2\n\\c 1\n\\p \\v 1 a\\u0020b caf\\u00e9 nul\\u0000x bad\\u00zzy "
            "big\\U0001F600z short\\u12 end\n")
    doc = usfmtc.readFile(usfm, informat="usfm")
    assert not doc.errors, doc.errors
    para = [e for e in doc.getroot() if e.tag == "para"][0]
    assert "".join(para.itertext()) == "a b café nul x bad y big\U0001F600z short  end"

def test_char_escapes_not_31():
    """ Before 3.2, \\u... is a marker as always """
    doc = usfmtc.readFile("\\id GEN test\n\\usfm 3.1\n\\c 1\n\\p \\v 1 caf\\u00e9\n", informat="usfm")
    assert any("u00e9" in e[0] for e in doc.errors)

def test_usfm_marker_not_an_escape():
    """ \\usfm and other markers starting with u aren't taken as escapes """
    doc = usfmtc.readFile("\\id GEN test\n\\usfm 3.2\n\\c 1\n\\p \\v 1 text\n", informat="usfm")
    assert not doc.errors and doc.getroot().get("version") == "3.2"

def test_parseas():
    """ parseas parses as that version whatever the \\usfm line says, and output keeps the declared version """
    usfm = "\\id GEN test\n\\usfm 3.1\n\\c 1\n\\p \\v 1 caf\\u00e9 a\\u005Cm b\n\\rem x \\zz|a\\* y\n"
    doc = usfmtc.readFile(usfm, informat="usfm", parseas="3.2")
    assert not doc.errors, doc.errors
    para = [e for e in doc.getroot() if e.tag == "para" and e.get("style") == "p"][0]
    assert "".join(para.itertext()).strip() == "café a\\m b"         # \m is a backslash and m, not \m
    out = doc.outUsfm(None)
    assert "\\usfm 3.1" in out and "café a\\\\m b" in out

def test_missing_fig_end():
    """ A \\fig whose attributes aren't followed by \\fig* says so """
    doc = usfmtc.readFile('\\id GEN t\n\\c 1\n\\p \\v 1 text \\fig A caption|src="x.jpg" size="col" ref="1.1" more\n',
                          informat="usfm")
    assert any("\\fig*" in e[0] for e in doc.errors), doc.errors

def test_bar_in_para_text():
    """ A | in paragraph text isn't blamed on a missing paragraph end marker """
    doc = usfmtc.readFile('\\id GEN t\n\\c 1\n\\m old | new\n', informat="usfm")
    assert not any("\\m*" in e[0] for e in doc.errors), doc.errors
