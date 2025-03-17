import pytest
from pytest import fail

from usfmtc.reference import Ref, RefList

def check_ref(ref, product=None, book=None, chapter=None, verse=None, subverse=None, word=None, char=None, mrkrs=None):
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

def test_basic():
    r = Ref("JHN 3:16")
    if not check_ref(r, None, "JHN", 3, 16):
        fail(f"{r} is not JHN 3:16")
    rr = Ref("12", context=r)
    if not check_ref(rr, None, "JHN", 3, 12):
        fail(f"{r} is not JHN 3:12")

def test_range():
    r = RefList("JHN 3:16-18")
    if not check_ref(r[0].first, None, "JHN", 3, 16):
        fail(f"{r[0].first} is not JHN 3:16")
    if not check_ref(r[0].last, None, "JHN", 3, 18):
        fail(f"{r[0].last} is not JHN 3:18")

