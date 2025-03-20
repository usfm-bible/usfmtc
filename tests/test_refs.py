import pytest
from pytest import fail
from usfmtc import readFile, usx2usfm
from usfmtc.usxmodel import findref, copy_range
from usfmtc.reference import Ref, RefList, RefRange
import os, io
import xml.etree.ElementTree as et

# To see the print() output of passing tests, run pytest -s

def check_ref(ref, product=None, book=None, chapter=None, verse=None, subverse=None,
                   word=None, char=None, mrkrs=None):
    if product != ref.product:
        return False
    if book != ref.book:
        return False
    if chapter != ref.chapter:
        return False
    if verse != ref.verse:
        return False
    if subverse != ref.subverse:
        return False
    if word != ref.word:
        return False
    if char != ref.char:
        return False
    return True

def asusfm(root):
    with io.StringIO() as fh:
        usx2usfm(fh, root)
        res = fh.getvalue()
    return res

jon_usfm = readFile(os.path.join(os.path.dirname(__file__), "32JONBSB.usfm"))

def test_basic():
    r = Ref("JHN 3:16")
    rr = Ref("12", context=r)

    if not check_ref(r, None, "JHN", 3, 16):
        fail(f"{r} is not JHN 3:16")
    if not check_ref(rr, None, "JHN", 3, 12):
        fail(f"{r} is not JHN 3:12")

def test_range():
    r = RefList("JHN 3:16-18")

    if not check_ref(r[0].first, None, "JHN", 3, 16):
        fail(f"{r[0].first} is not JHN 3:16")
    if not check_ref(r[0].last, None, "JHN", 3, 18):
        fail(f"{r[0].last} is not JHN 3:18")

def test_findreftext():
    r = Ref("JON 3:6!3")
    loc = findref(r, jon_usfm.getroot())

    if loc.el.tag != "verse" and loc.attrib != " tail" and loc.char != 18:
        fail(f"{r} resulted in {loc}")
    end = Ref("JON 3:6!4")
    eloc = findref(end, jon_usfm.getroot(), atend=True)
    if eloc.el.tag != "verse" and eloc.attrib != " tail" and eloc.char !=24:
        fail(f"{end} resulted in {eloc}")
    res = eloc.el.tail[loc.char:eloc.char]
    if res != "reached the":
        fail(f"{res} != 'reached the'")

def test_findref1():
    first = Ref("JON 2:8")
    last = Ref("JON 2")
    _do_findreftest(first, last)

def test_findref2():
    ref = Ref("JON 2:8-end")
    _do_findreftest(ref.first, ref.last)

def test_getrefs():
    refs = RefList("JON 1:3; 2:4-5; 3:9-end")
    res = jon_usfm.getrefs(*refs)
    root = res.getroot()
    print(res.outUsfm())
    if len(root) != 14 or root[0].get("vid", "") != "JON 1:3":
        fail(f"{len(root)=}")

def _do_findreftest(first, last):
    root = jon_usfm.getroot()
    start = findref(first, root)
    end = findref(last, root, atend=True)
    res = copy_range(root, start, end)

    print(f"{first=} {start}; {last=} {end}")
    et.dump(res)
    print(asusfm(res))
    if len(res) != 7 or len(res[2]) != 1 or "vomited" not in res[-1][-1].tail:
        fail(f"{len(res)=}, {res[-1][-1].tail=}")

def r(bk, chap, verse, subv=None):
    return Ref(book=bk, chapter=chap, verse=verse, subverse=subv)

def t(s, *r):
    res = RefList(s)
    if len(res) != len(r):
        fail("Failed '{}' resulted in {} references, {}, rather than {}".format(s, len(res), res, len(r)))
    for z in zip(res, r):
        if z[0] != z[1]:
            fail("Reference list failed '{}', {} != {}".format(s, z[0], z[1]))
    if str(res) != s:
        fail("{} != canonical string of {}".format(s, str(res)))
    print("{} = {}".format(s, str(res)))

def listtest(s, a):
    res = RefList(s)
    res.simplify()
    base = RefList(a)
    if res != base:
        fail("{} simplified to {} instead of {}".format(s, res, base))
    print("{} -> {}".format(s, res))

def o(a, b, res):
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

def test_gen1():
    t("GEN 1:1", r("GEN", 1, 1))

def test_jhn3():
    t("JHN 3", r("JHN", 3, None))

def test_3jn():
    t("3JN 3", r("3JN", 1, 3))

def test_1co():
    t("1CO 6:5a", r("1CO", 6, 5, "a"))

def test_mat5():
    t("MAT 5:1-7", RefRange(r("MAT", 5, 1), r("MAT", 5, 7)))

def test_mat7():
    t("MAT 7:1,2; 8:6b-9:4", r("MAT", 7, 1), r("MAT", 7, 2), RefRange(r("MAT", 8, 6, "b"), r("MAT", 9, 4)))

def test_luk3():
    t("LUK 3:35-end", RefRange(r("LUK", 3, 35), r("LUK", 3, -1)))

def test_rom1():
    listtest("ROM 1; MAT 3:4-11; ROM 1:3-2:7", "MAT 3:4-11; ROM 1-2:7")

def test_gen1_1():
    t("GEN 1:1-3; 3:2-11; LUK 4:5", RefRange(r("GEN", 1, 1), r("GEN", 1, 3)), RefRange(r("GEN", 3, 2), r("GEN", 3, 11)), r("LUK", 4, 5))

def test_jud():
    t("JUD 1,2,4", r("JUD", 1, 1), r("JUD", 1, 2), r("JUD", 1, 4))

def test_gen1_1a():
    o("GEN 1:1", "EXO 2:3", (True,False,False))

def test_exo2():
    o("EXO 2:4", "EXO 2", (False,True,True))

def test_exo2a():
    o("EXO 2:4-5", "EXO 2", (False,True,True))

def test_exo2b():
    o("EXO 2:4-5", "EXO 3", (True,False,False))

def text_exo2c():
    o("EXO 2:1-2", "EXO 2:1-5", (False,False,True))

def test_exo2d():
    o("EXO 2:1-2", "EXO 2:2-7", (True,False,True))

def test_exo2e():
    o("EXO 2:1-2", "EXO 2:3-6", (True,False,False))

def test_gen2():
    o("GEN 2:1-2", "EXO 2:3-6", (True,False,False))

def test_deu2():
    o("DEU 2:1-2", "EXO 2:3-6", (False,True,False))

def test_exo2f():
    o("EXO 2:2-3", "EXO 2:1-5", (False,False,True))


