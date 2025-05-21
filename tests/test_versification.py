import pytest
from pytest import fail
from usfmtc.reference import Ref
from usfmtc.versification import Versification
import os

engvrs = Versification(os.path.join(os.path.dirname(__file__), "eng.vrs"))

def test_engmap1():
    r = Ref("ISA 64:3")
    res = engvrs.remap(r)
    if str(res) != "ISA 64:2":
        fail(f"{r} remaps to {res} instead of ISA 64:2")

def test_engmapr1():
    r = Ref("ISA 64:3")
    res = engvrs.remap(r, engvrs)
    if str(res) != "ISA 64:3":
        fail(f"{r} remaps to {res} instead of ISA 64:3")
