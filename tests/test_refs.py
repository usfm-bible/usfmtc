import pytest
from pytest import fail
from usfmtc import readFile, usx2usfm
from usfmtc.usxmodel import findref, copy_range
from usfmtc.reference import Ref, RefList
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
    ref = RefList("JON 2:8-end")[0]
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
