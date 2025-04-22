import pytest
from pytest import fail
from usfmtc import readFile, usx2usfm
from usfmtc.usxmodel import getoblinkages
from usfmtc.usfmparser import Grammar
import xml.etree.ElementTree as et

grammar = Grammar()
for a in ("", "-s", "-e"):
    grammar.marker_categories["za"+a] = "milestone"

def _dotest(txt, links):
    doc = readFile(txt, informat="usfm", grammar=grammar)
    doc.canonicalise()
    r = doc.getroot()
    et.dump(r)
    tlinks = getoblinkages(r, doc.book)
    et.dump(r)
    passed = True
    for k, v in tlinks.items():
        print(f"{k[1]}[{k[0]}] = {v}")
        if k not in links or str(v) != links[k]:
            passed = False
    if not passed:
        fail(f"Linkages: {tlinks} are not the same as the expected {links}")

def test_link_simple():
    usfm = r"""\id JHN A test of John
\c 3
\p
\v 7 This is \za-s|id="a001" type="comment"\*the\za-e|id="a001" type="comment"\* bo\za-s|id="a002" type="comment"\*ok to re\za-e|id="a002" type="comment"\*ad"""
    _dotest(usfm, {("a001", "comment"): "JHN 3:7!3", ("a002", "comment"): "JHN 3:7!4+2-6+2"})

