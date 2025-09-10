import pytest
from pytest import fail
from usfmtc import readFile, usx2usfm
from usfmtc.usxcursor import USXCursor
from usfmtc.reference import Ref, RefList, RefRange
import os, io
import xml.etree.ElementTree as et

# To see the print() output of passing tests, run pytest -s

def check_ref(ref, product=None, book=None, chapter=None, verse=None, subverse=None,
                   word=None, char=None, mrkrs=None):
    r = Ref(product=product, book=book, chapter=chapter, verse=verse, subverse=subverse,
                    word=word, char=char, mrkrs=mrkrs)
    return r == ref

def asusfm(root):
    with io.StringIO() as fh:
        usx2usfm(fh, root)
        res = fh.getvalue()
    return res

jon_usfm = readFile(os.path.join(os.path.dirname(__file__), "32JONBSB.usfm"))

def _get_textref(s):
    r = Ref(s)
    root = jon_usfm.getroot()
    start = USXCursor.fromRef(r.first, jon_usfm)
    end = USXCursor.fromRef(r.last, jon_usfm, atend=True)
    print(start, end)
    res = start.copy_text(root, end)
    return r, res

def _r(bk, chap, verse, subv=None):
    return Ref(book=bk, chapter=chap, verse=verse, subverse=subv)

def _t(s, *r):
    res = RefList(s)
    if len(res) != len(r):
        fail("Failed '{}' resulted in {} references, {}, rather than {}".format(s, len(res), res, len(r)))
    for z in zip(res, r):
        if z[0] != z[1]:
            fail("Reference list failed '{}', {} != {}".format(s, z[0], z[1]))
    if str(res) != s:
        fail("{} != canonical string of {}".format(s, str(res)))
    print("{} = {}".format(s, str(res)))

def _listtest(s, a):
    res = RefList(s)
    res.simplify()
    base = RefList(a)
    if res != base:
        fail("{} simplified to {} instead of {}".format(s, res, base))
    print("{} -> {}".format(s, res))

def _o(a, b, res):
    x = RefList(a)[0]
    y = RefList(b)[0]
    if (isinstance(res,tuple)):
      restup=res
      restupd=f"x<y {restup[0]}, y<x {restup[1]}, x in y {restup[2]}"
    else:
      restup=(res,res,res)
      restupd=res
    a = (y<x)
    b = (x<y)
    #print(f"y<x :{a} x<y:{b}")
    if restup[0] != b:
        raise fail(f"{x} should be < {y} [expect: {restupd}]")
    if restup[1] != a:
        raise fail(f"{y} should not be < {x} [expect: {restupd}]")
    if (x in y) != restup[2]:
        raise fail(f"{x} in {y} should be {res}")
    print("{} <-> {} ({})".format(x, y,restupd))

def _do_findreftest(ref):
    res = jon_usfm.getrefs(ref, titles=False).xml
    et.dump(res)
    print(asusfm(res))
    if len(res) != 7 or len(res[2]) != 1 or "vomited" not in res[-1][-1].tail:
        fail(f"{len(res)=}, {res[-1][-1].tail=}")

def _type_test(srange, ref, text):
    tdoc = jon_usfm.getrefs(srange, titles=False)
    loc = USXCursor(ref, tdoc)
    tdoc.insert_text(loc, text)
    return tdoc

#### The tests

def test_basic():
    r = Ref("JHN 3:16")
    rr = Ref("12", context=r)

    if not check_ref(r, None, "JHN", 3, 16):
        fail(f"{r} is not JHN 3:16")
    if not check_ref(rr, None, "JHN", 3, 12):
        fail(f"{rr} is not JHN 3:12")

def test_range():
    r = RefList("JHN 3:16-18")

    if not check_ref(r[0].first, None, "JHN", 3, 16):
        fail(f"{r[0].first} is not JHN 3:16")
    if not check_ref(r[0].last, None, "JHN", 3, 18):
        fail(f"{r[0].last} is not JHN 3:18")

def test_findreftext():
    r = Ref("JON 3:6!3")
    loc = USXCursor.fromRef(r, jon_usfm)

    if loc.el.tag != "verse" and loc.attrib != " tail" and loc.char != 18:
        fail(f"{r} resulted in {loc}")
    end = Ref("JON 3:6!4")
    eloc = USXCursor.fromRef(end, jon_usfm, atend=True)
    if eloc.el.tag != "verse" and eloc.attrib != " tail" and eloc.char !=24:
        fail(f"{end} resulted in {eloc}")
    res = eloc.el.tail[loc.char:eloc.char]
    if res != "reached the":
        fail(f"{res} != 'reached the'")

def test_findref2():
    ref = Ref("JON 2:8-end")
    _do_findreftest(ref)

def test_getrefs():
    refs = list(RefList("JON 1:3; 2:4-5; 3:9-end"))
    res = jon_usfm.getrefs(*refs)
    root = res.getroot()
    print(res.outUsfm())
    print(res.outUsx())
    if len(root) != 17 or root[5].get("vid", "") != "JON 1:3":
        fail(f"{len(root)=}")

def test_textref1():
    r = Ref("JON 2:8!2-4")
    res = jon_usfm.gettext(r)
    print(res)
    if res != "who cling to":
        fail(f"Text not found. Got '{res}'")

def test_gen1():
    _t("GEN 1:1", _r("GEN", 1, 1))

def test_jhn3():
    _t("JHN 3", _r("JHN", 3, None))

def test_3jn():
    _t("3JN 3", _r("3JN", 1, 3))

def test_1co():
    _t("1CO 6:5a", _r("1CO", 6, 5, "a"))

def test_mat5():
    _t("MAT 5:1-7", RefRange(_r("MAT", 5, 1), _r("MAT", 5, 7)))

def test_mat7():
    _t("MAT 7:1,2; 8:6b-9:4", _r("MAT", 7, 1), _r("MAT", 7, 2), RefRange(_r("MAT", 8, 6, "b"), _r("MAT", 9, 4)))

def test_luk3():
    _t("LUK 3:35-end", RefRange(_r("LUK", 3, 35), _r("LUK", 3, -1)))

def test_rom1():
    _listtest("ROM 1; MAT 3:4-11; ROM 1:3-2:7", "MAT 3:4-11; ROM 1-2:7")

def test_gen1_1():
    _t("GEN 1:1-3; 3:2-11; LUK 4:5", RefRange(_r("GEN", 1, 1), _r("GEN", 1, 3)), RefRange(_r("GEN", 3, 2), _r("GEN", 3, 11)), _r("LUK", 4, 5))

def test_jud():
    _t("JUD 1,2,4", _r("JUD", 1, 1), _r("JUD", 1, 2), _r("JUD", 1, 4))

def test_gen1_1a():
    _o("GEN 1:1", "EXO 2:3", (True,False,False))

def test_exo2():
    _o("EXO 2:4", "EXO 2", (False,True,True))

def test_exo2a():
    _o("EXO 2:4-5", "EXO 2", (False,False,True))

def test_exo2b():
    _o("EXO 2:4-5", "EXO 3", (True,False,False))

def text_exo2c():
    _o("EXO 2:1-2", "EXO 2:1-5", (False,False,True))

def test_exo2d():
    _o("EXO 2:1-2", "EXO 2:2-7", (False,False,False))

def test_exo2e():
    _o("EXO 2:1-2", "EXO 2:3-6", (True,False,False))

def test_gen2():
    _o("GEN 2:1-2", "EXO 2:3-6", (True,False,False))

def test_deu2():
    _o("DEU 2:1-2", "EXO 2:3-6", (False,True,False))

def test_exo2f():
    _o("EXO 2:2-3", "EXO 2:1-5", (False,False,True))

def test_exo27():
    _t("EXO 27:5; 38:1-6", _r("EXO", 27, 5), RefRange(_r("EXO", 38, 1), _r("EXO", 38, 6)))

# ChatGPT tests:
def test_invalid_ref():
    try:
        r = Ref("INVALID 1:1")
        fail("Invalid reference did not raise an error")
    except SyntaxError:
        pass

def test_cross_book_range():
    r = Ref("JON 3:10 - MIC 1:2", bookranges=True)
    if not check_ref(r.first, None, "JON", 3, 10):
        fail(f"{r.first} is not JON 3:10")
    if not check_ref(r.last, None, "MIC", 1, 2):
        fail(f"{r.last} is not MIC 1:2")

def test_partial_chapter():
    r = Ref("JON 2")
    if not check_ref(r.first, None, "JON", 2, None):
        fail(f"{r.first} is not JON 2")

def test_textref_boundary():
    r, res = _get_textref("JON 3:10!1-2")
    print(res)
    if res != "When God":
        fail(f"{r}: Unexpected result: {res}")

def test_multiple_ranges():
    refs = RefList("JON 1:1-3; 2:4; 3:8-end")
    res = jon_usfm.getrefs(*refs, titles=False)
    root = res.getroot()
    et.dump(root)

    if len(root) != 12 or root[3].get("vid", "") != "JON 1:1":
        fail(f"Incorrect range extraction: {len(root)=}")

def test_chapter_only_range():
    r = Ref("JON 3").expand()
    if not check_ref(r.first, None, "JON", 3, 1):
        fail(f"{r.first} is not JON 3:1")

def test_single_verse():
    r = Ref("JON 1:1")
    if not check_ref(r.first, None, "JON", 1, 1):
        fail(f"{r.first} is not JON 1:1")

def test_multi_book_list():
    refs = RefList("JON 1:1; MIC 2:3; NAH 1:7")
    if len(refs) != 3:
        fail("Expected three references")

def test_edge_case_verse():
    r = Ref("JON 4:11")
    if not check_ref(r.first, None, "JON", 4, 11):
        fail(f"{r.first} is not JON 4:11")

def test_reverse_range():
    try:
        r = RefList("JON 3:5 - JON 2:1")
        fail("Reverse range did not raise an error")
    except ValueError:
        pass

def test_reference_with_suffix():
    r = Ref("JON 3:10a")
    if not check_ref(r.first, None, "JON", 3, 10):
        fail(f"{r.first} is not JON 3:10a")
    if not check_ref(r.first, None, "JON", 3, 10, "a"):
        fail(f"{r.first} is not JON 3:10")

def test_overlapping_ranges():
    refs = RefList("JON 1:3-5; 1:4-6")
    if len(refs) != 2:
        fail("Expected two overlapping references")

def test_whitespace_in_ref():
    try:
        r = Ref("  JON   2 :  3 ")
        fail(f"{r.first} has whitespace in it and should fail")
    except SyntaxError:
        pass

def test_missing_chapter():
    try:
        r = Ref("JON :5")
        fail("Missing chapter did not raise an error")
    except SyntaxError:
        pass

def test_long_reference():
    r = RefList("JON 1:1-4:11")
    if not (check_ref(r[0].first, None, "JON", 1, 1) and check_ref(r[0].last, None, "JON", 4, 11)):
        fail("Long reference not parsed correctly")

@pytest.mark.skip
def test_empty_reference():
    try:
        r = Ref("")
        fail("Empty reference did not raise an error")
    except SyntaxError:
        pass

def test_invalid_book_code():
    r = Ref("XYZ 1:1")
    if r.isvalid():
        fail("Invalid book code did not raise an error")

def test_multiple_chapters():
    refs = RefList("JON 2:1-3:5")
    if not (check_ref(refs[0].first, None, "JON", 2, 1) and check_ref(refs[0].last, None, "JON", 3, 5)):
        fail("Multiple chapters not handled correctly")

def test_partial_verse():
    r = Ref("JON 3:10!1-4")
    res = jon_usfm.gettext(r)
    if "God" not in res:
        fail(f"Partial verse not extracted correctly. Got '{res}'")

def test_ref_with_extra_text():
    try:
        r = Ref("JON 3:10abc")
        fail(f"Reference {r} with extra text did not raise an error")
    except SyntaxError:
        pass

def test_range_with_negative_chapter():
    try:
        r = Ref("JON -1:5")
        fail(f"Negative chapter did not raise an error. Got {r}")
    except SyntaxError:
        pass

@pytest.mark.skip
def test_incomplete_reference():
    try:
        r = Ref("JON")
        fail("Incomplete reference did not raise an error")
    except SyntaxError:
        pass

def test_large_chapter_number():
    r = Ref("JON 999:1")
    if r.isvalid():
        fail("Large chapter number did not raise an error")

### Markers

def test_parsemarker():
    r, res = _get_textref("JON 1:4!s1!2")
    if res != "Great":
        fail(f"{r}: {res}")

def test_footnote1():
    r, res = _get_textref("JON 1:13!f!5")
    if res != "dug":
        fail(f"{r}: {res}")

# @pytest.mark.skip
def test_footnote2():
    r, res = _get_textref("JON 1:13!5!f!5")
    if res != "dug":
        fail(f"{r}: {res}")

def test_verselist():
    r = Ref("JHN 3:16,17,18")
    if str(r.last) != "JHN 3:18":
        fail(f"{r}")

def test_badverselist():
    try:
        r = Ref("JHN 3:16,18")
        fail("Non contigous list returned {r}")
    except SyntaxError:
        pass

def test_goodreflistattr():
    r = RefList("JHN 3:16, 19, 30", strict=False)
    if r.chapter != 3:
        fail("The chapter of {r} is not 3")

def test_badreflistattr():
    r = RefList()
    try:
        x = r.chapter
        fail("Empty RefList has chapter {x}")
    except AttributeError:
        pass

def test_unequalrangeattr():
    r = Ref("JHN 3:16-4:3", strict=True)
    try:
        x = r.chapter
        fail("Unequal chapters in RefRange returned {x}")
    except AttributeError:
        pass

def test_reflistspace():
    r = RefList("MRK PHP 1JN 2JN 3JN JUD", sep=" ")
    print(r)
    if len(r) != 6:
        fail(f"{r} should have 6 books in it")

def test_reflistcomma():
    r = RefList("GEN 1-10 LUK, 2JN REV 3-13", sep=" ")
    print(r)
    if len(r) != 4:
        fail(f"{r} should have 4 books in it")

def test_refbidi():
    r = Ref("GEN 1:22\u200F-23")
    if r.sep != "\u200F-" or "\u200F" not in str(r):
        fail(f"{r} should contain bidi control")

def test_reflistref():
    r = Ref("GEN 1:1-20,13,19")
    print(r)
    if r.last != Ref("GEN 1:20"):
        fail(f"{r} is not GEN 1:1-20")

def test_reflistsimplify():
    r = RefList("JHN 3:16 GEN 1:1, PSA 23 ISA 53 PSA 23:1")
    r.simplify()
    print(r)
    if len(r) != 4 or r[1].first.verse is not None or r[1].first != r[1].last:
        fail(f"{r} is not simple")

def test_isvalid():
    r = Ref("PSA 23:10")
    if r.isvalid():
        fail(f"{r} should not be valid")

def test_subdoc1():
    res = jon_usfm.getrefs(*RefList("JON 1:4-8; 4:9-11"), headers=True, titles=False)
    et.dump(res.xml)
    f = res.outUsfm(None, forcevid=True)
    print(f)
    if "Acts 27:13-26" not in f and "vid|JON 4:9" not in f:
        fail(f"{f} does not contain section heads or the right vid markers")
    if f.count('vid') != 2:
        fail(f"{f} wrong number of \\vid in the text")

def test_finalv():
    res = jon_usfm.getrefs(Ref("JON 1:17"), titles=False)
    et.dump(res.xml)
    f = res.outUsfm(None, forcevid=True)
    print(f)
    if "\\c" in f:
        fail(f"{f} contains more than text")

def test_booklist():
    r = RefList("GEN EXO LEV NUM PSA")
    r.simplify()
    if len(r) != 5:
        fail(f"{r} doesn't have 5 books")
    r.simplify(bookranges=True)
    if len(r) != 2:
        fail(f"{r} should have 2 elements")

def test_rangebooks():
    r = RefList("2JN 1-3JN 14")
    r.simplify()
    if len(r) != 2:
        fail(f"{r} should have 2 elements")

def test_rangeseq():
    r = RefList("DEU 16:1, 19:1, 2, 3, 4")
    r.simplify()
    print(r.str())
    if "19-2" in str(r):
        fail(f"{r} has {len(r)} refs: {r[0]}, {r[1]}")
