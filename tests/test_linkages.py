import pytest
from pytest import fail
import io
from usfmtc import readFile, usx2usfm
from usfmtc.usxmodel import getlinkages, insertlinkages
from usfmtc.usfmparser import Grammar
from usfmtc.reference import Ref
import xml.etree.ElementTree as et

grammar = Grammar()
for a in ("", "-s", "-e"):
    grammar.marker_categories["za"+a] = "milestone"
    grammar.attribmap["za"+a] = "aid"

def asusfm(root, grammar=None):
    if grammar is None:
        grammar = usfmtc.Grammar()
    with io.StringIO() as fh:
        usx2usfm(fh, root, grammar)
        res = fh.getvalue()
    return res

def _dotest(txt, links, skipsfmequal=False):
    doc = readFile(txt, informat="usfm", grammar=grammar)
    doc.canonicalise()
    r = doc.getroot()
    tinit = asusfm(r, grammar)
    et.dump(r)
    tlinks = getlinkages(r, doc.book)
    et.dump(r)
    passed = True
    for k, v in tlinks.items():
        print(f"{k[1]}[{k[0]}] = {v} | {links.get(k,'')}")
        if k not in links or v.str(force=1) != links[k]:
            print(f"{v.str(force=1)} != {links[k]}")
            passed = False
    if not passed or len(tlinks) != len(links):
        fail(f"Linkages: {tlinks} are not the same as the expected {links}")
    mlinks = []
    for k, v in tlinks.items():
        if v.first != v.last or v.word is None or v.char is None:
            mlinks.append((v.first, "za-s", False, k[0], k[1]))
            mlinks.append((v.last, "za-e", True, k[0], k[1]))
        else:
            mlinks.append((v.first, "za", False, k[0], k[1]))
    insertlinkages(r, mlinks, bk=doc.book, grammar=grammar)
    if not skipsfmequal:
        t = asusfm(r, grammar)
        if t != tinit:
            fail(f"{t}\n is not the same as\n{tinit}")
    

def test_link_simple():
    usfm = r"""\id JHN A test of John
\c 3
\p
\v 7 This is \za-s|aid="a001" type="comment"\*the\za-e|aid="a001" type="comment"\*
     bo\za-s|aid="a002" type="comment"\*ok to re\za-e|aid="a002" type="comment"\*ad"""
    _dotest(usfm, { ("a001", "comment"): "JHN 3:7!3",
                    ("a002", "comment"): "JHN 3:7!4+2-6+2"})

def test_link_romani():
    usfm = r"""\id JHN John test
\c 2
\p
\v 24 \za|6ffadcab\*\za|1762aaba\*\za|77934015\*Atunći von phende \za-s|b596c2a4\*maśkar
      penθe\za-e|b596c2a4\*: <<Te na \za-s|ee26b6ce\*ćhinas\za-e|ee26b6ce\* les!
      Te \za|ede7da9b\*\za|5579cb82\*\za|c27de536\*\za-s|3d2b3153\*dikhas\za-e|3d2b3153\* kasqe
      \za|ce0acfa6\*perel\za|29692144\*!>> \za-s|cc7d236e\*Kadja vi sas,\za-e|cc7d236e\*
      kaś te kerel pes so sas \za|8ad89bbc\*xramosardo \za-s|8be39bed\*and-o\za-e|8be39bed\*
      Lil le Devlesqo, \za-s|e6a77bca\*savo phenel\za-e|e6a77bca\*:
\q1 \qt {\za-s|85a815f7\*Mirre\za-e|85a815f7\* \za-s|38c4ff42\*sumagǎ\za-e|38c4ff42\*//
      maśkar \za-s|90fbe824\*penθe\za-e|90fbe824\* xulavde,\za|8206cdd4\*\qt*
\q2 \qt \za-s|afcccf77\*haj\za-e|afcccf77\*Mirro gad// kasqe perel, von dikhle.}\qt*\x + \xo 19:24 \xt Psa 22:18.\xt*\x*
\m \za-s|9deaa4bd\*Kadja\za-e|9deaa4bd\* vi kerde ol soldaturǎ."""
    _dotest(usfm, {
                ("77934015", "unk"): "JHN 2:24!1+0",
                ("1762aaba", "unk"): "JHN 2:24!1+0",
                ("6ffadcab", "unk"): "JHN 2:24!1+0",
                ("b596c2a4", "unk"): "JHN 2:24!4-5+5",
                ("ee26b6ce", "unk"): "JHN 2:24!8",
                ("c27de536", "unk"): "JHN 2:24!11+0",
                ("5579cb82", "unk"): "JHN 2:24!11+0",
                ("ede7da9b", "unk"): "JHN 2:24!11+0",
                ("3d2b3153", "unk"): "JHN 2:24!11",
                ("ce0acfa6", "unk"): "JHN 2:24!13+0",
                ("29692144", "unk"): "JHN 2:24!13+5",
                ("cc7d236e", "unk"): "JHN 2:24!14-16",
                ("8ad89bbc", "unk"): "JHN 2:24!23+0",
                ("8be39bed", "unk"): "JHN 2:24!24",
                ("e6a77bca", "unk"): "JHN 2:24!28-29+6",
                ("85a815f7", "unk"): "JHN 2:24!30+1-6",
                ("38c4ff42", "unk"): "JHN 2:24!31",
                ("90fbe824", "unk"): "JHN 2:24!33",
                ("8206cdd4", "unk"): "JHN 2:24!34+8",
                ("afcccf77", "unk"): "JHN 2:24!35+1-3",
                ("9deaa4bd", "unk"): "JHN 2:24!41",
                  }, skipsfmequal=True)

def test_link_note():
    usfm = r"""\id JHN notes
\c 17
\p
\v 6 This is some text\f + \fr 17:6 \ft Which is \za-s|1234\*clearly\za-e|1234\* not the actual text\f* to test with."""
    _dotest(usfm, {
                ('1234', 'unk'): "JHN 17:6!f!4"
                  })


