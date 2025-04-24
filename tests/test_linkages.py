import pytest
from pytest import fail
import io
from usfmtc import readFile, usx2usfm
from usfmtc.usxmodel import getoblinkages, insertoblinkages
from usfmtc.usfmparser import Grammar
from usfmtc.reference import Ref
import xml.etree.ElementTree as et

grammar = Grammar()
for a in ("", "-s", "-e"):
    grammar.marker_categories["za"+a] = "milestone"

def asusfm(root, grammar=None):
    if grammar is None:
        grammar = usfmtc.Grammar()
    with io.StringIO() as fh:
        usx2usfm(fh, root, grammar)
        res = fh.getvalue()
    return res

def _dotest(txt, links):
    doc = readFile(txt, informat="usfm", grammar=grammar)
    doc.canonicalise()
    r = doc.getroot()
    tinit = asusfm(r, grammar)
    et.dump(r)
    tlinks = getoblinkages(r, doc.book)
    et.dump(r)
    passed = True
    for k, v in tlinks.items():
        print(f"{k[1]}[{k[0]}] = {v}")
        if k not in links or str(v) != links[k]:
            passed = False
    if not passed or len(tlinks) != len(links):
        fail(f"Linkages: {tlinks} are not the same as the expected {links}")
    mlinks = {}
    for k, v in tlinks.items():
        ref = v
        vlist = mlinks.setdefault(ref.first.chapter, {}).setdefault(ref.first.verse, [])
        vlist.append((str(ref.first), str(ref.last) if ref.first != ref.last else "", k[0], k[1]))
    insertoblinkages(r, mlinks, bk=doc.book, grammar=grammar)
    t = asusfm(r, grammar)
    if t != tinit:
        fail(f"Linkages: {t} is not the same as {txt}")
    

def test_link_simple():
    usfm = r"""\id JHN A test of John
\c 3
\p
\v 7 This is \za-s|id="a001" type="comment"\*the\za-e|id="a001" type="comment"\*
     bo\za-s|id="a002" type="comment"\*ok to re\za-e|id="a002" type="comment"\*ad"""
    _dotest(usfm, { ("a001", "comment"): "JHN 3:7!3",
                    ("a002", "comment"): "JHN 3:7!4+2-6+2"})

