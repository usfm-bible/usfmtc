import pytest
from pytest import fail
from usfmtc import readFile
from usfmtc.reference import Ref
from usfmtc.versification import Versification
from usfmtc.usxmodel import etCmp
import os

engvrs = Versification(os.path.join(os.path.dirname(__file__), "eng.vrs"))
jon_usfm = readFile(os.path.join(os.path.dirname(__file__), "32JONBSB.usfm"))

def test_engmap1():
    r = Ref("ISA 64:3")
    res = engvrs.remap(r, None)
    if str(res) != "ISA 64:2":
        fail(f"{r} remaps to {res} instead of ISA 64:2")

def test_engmapr1():
    r = Ref("ISA 64:3")
    res = engvrs.remap(r, engvrs)
    if str(res) != "ISA 64:3":
        fail(f"{r} remaps to {res} instead of ISA 64:3")

def test_reversify1():
    jtest = jon_usfm.copy(deep=True)
    jtest.reversify(engvrs, None)
    print(jtest.outUsfm())
    res = jtest.gettext(Ref("JON 2:11"))
    if not len(res):
        fail(f"Failed to find JON 2:11, due to reversify error")
    jtest.reversify(None, engvrs)
    print(jtest.outUsfm())
    if not etCmp(jtest.getroot(), jon_usfm.getroot(), verbose=True):
        fail(f"Unreversified text difference")

def test_engmap2():
    r = Ref("ISA 64:1")
    res = engvrs.remap(r, engvrs)
    if str(res) != "ISA 64:1":      # we don't want to delete it, delete v2 instead
        fail(f"{r} remaps to {res} instead of ISA 64:1")
