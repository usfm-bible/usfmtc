import pytest
from pytest import fail
import io
from usfmtc import readFile, usx2usfm
from usfmtc.usxmodel import getlinkages, insertlinkages
from usfmtc.usfmparser import Grammar
from usfmtc.reference import Ref, RefList
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
    tlinks = getlinkages(doc)
    et.dump(r)
    passed = True
    for k, v in tlinks.items():
        print(f"{k[1]}[{k[0]}] = {v.str(force=1)} | {links.get(k,'')}")
        if k not in links or v.str(force=1) != links[k]:
            print(f"{v.str(force=1)} != {links[k]}")
            passed = False
    if not passed or len(tlinks) != len(links):
        fail(f"Linkages: {tlinks} are not the same as the expected {links}")
    mlinks = []
    for k, v in tlinks.items():
        if v.first != v.last or v.getword(None) is None or v.getchar(None) is None:
            mlinks.append((v.first, "za-s", False, k[0], k[1]))
            mlinks.append((v.last, "za-e", True, k[0], k[1]))
        else:
            mlinks.append((v.first, "za", False, k[0], k[1]))
    insertlinkages(doc, mlinks)
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
                ("77934015", "unk"): "JHN 2:24!0",
                ("1762aaba", "unk"): "JHN 2:24!0",
                ("6ffadcab", "unk"): "JHN 2:24!0",
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
                ("85a815f7", "unk"): "JHN 2:24!q1!1+1-6",
                ("38c4ff42", "unk"): "JHN 2:24!q1!2",
                ("90fbe824", "unk"): "JHN 2:24!q1!4",
                ("8206cdd4", "unk"): "JHN 2:24!q1!5+8",
                ("afcccf77", "unk"): "JHN 2:24!q2!1-3",
                ("9deaa4bd", "unk"): "JHN 2:24!m!1",
                  }, skipsfmequal=True)

def test_link_note():
    usfm = r"""\id JHN notes
\c 17
\s1 The Great \za-s|1235\*High Priestly\f + \fr 17:6 \ft Not the greatest of names\za|1236\*\f*\za-e|1235\* Prayer
\p
\v 6 This is some text\f + \fr 17:6 \ft Which is \za-s|1234\*clearly\za-e|1234\* not the actual text\f* to test with."""
    _dotest(usfm, {
                ('1234', 'unk'): "JHN 17:6!f!4",
                ('1235', 'unk'): "JHN 17:6!s1!3-4",
                ('1236', 'unk'): "JHN 17:6!s1!4+8!f!6+5"
                  }, skipsfmequal=True)

def test_link_intro():
    usfm = r'''\id PHM WSG Adilabad Gondi (Telangana, India) (C) 2010-2018 SIL SAG CIC WSG Team 
\h pilemōn 
\toc1 pilemōntun lihi kīta ciṭi 
\toc2 pilemōn 
\toc3 pilemōn 
\mt1 pilemōn 
\mt2 pilemōntun lihi kīta ciṭi 
\is ciṭitun bāreta gosṭi 
\im \k lihi kītona porol: \k* pavlu 
\im \k lihi \za-s|001\*kīta\za-e|001\* sāl: \k* kiristu sakam lag-bag sāṭ (60) sāldaga lihi kiyval jargta. 
\im \k muke gosṭi:\k* pavlu jēldaga maneke id ciṭi lihi kītor. \za-s|002\*pilemōntur\za-e|002\* dāsirgaṭal onesīmon inval dāsi-māynal parar āsi, pavlu manval jāgataga vātor. pavlu yēsun bāreta cokoṭna kabur vōn vehtor. aske vōr onesīm yēsun poro barosa irtor. te iṅke pavlu onesīmontun vōnor mālkanaga sāri kīser mantor. onesīmon itteke, «pāyda siyval» injer artam. iden mune onesīmon pilemōnta kāmun cukḍi kiyval āsi mattor. bati iṅke bagavantana permata-dayate pavlun, pilemōntun ani vīrgaṭal ter yēsu parbunte vele pāyda siyval ātor. onesīmontun māpi kīsi, kāmnaga malsi yētana injer pilemōntun, id ciṭi pavlu lihi kītor. 
\iot baga batal manta 
\io1 daṇḍosk \ior 1-3 \ior* 
\io1 \za-s|003\*pārtana ani danevād\za-e|003\* \ior 4-7 \ior* 
\io1 onesīmon sāṭi vinanti kiyval \ior 8-25 \ior*
\c 1 
\s daṇḍosk'''
    _dotest(usfm, {
                ('001', 'unk') : "PHM 0!im[2]!2",
                ('002', 'unk') : "PHM 0!im[3]!10",
                ('003', 'unk') : "PHM 0!io1[2]!1-3"
                  })

def test_getrefspsa():
    usfm = r'''\id PSA - Pukapuka Bible
\c 43
\s E tatakunga ki te Atua i te vāia tūngayala
\r (Te wakayawenga o te Talamo 42)
\q1
\v 1 E toku Atua ē, wakatika mai koe kāe oku takayala,
\q2 wakamamata koe i toku tū tautonu ki te wenua atuakole nei.
\q2 Wakaola ake au mai te kau vativati ma te waiva kikino nei.
\c 44
\s E tatakunga kē paletuangia te wenua
\d Ki te wakayaele yīmene, ko nā tama a \w Kola\w* na watua.
\q1
\v 1 E te Atua ē, na langona e o~mātou talinga,
\q2 na tala mai oki e o~mātou mātutua tupuna
\q1 au wī yanga nā wai i tō lātou vāia,
\q2 i nā ayo o \w Uwikelé|Uwikele\w*.
\c 45
\s E yīmene wakaaonga nō te aliki
\d Ki te wakayaele yīmene, ko nā tama a \w Kola\w* na watua ki te tiūnu, “Ko nā tiale lili.”
\q1
\v 1 Na kamuloa toku ngākau ngalepu wua i te manatunga lelei nei
\q2 kē watu au e yikunga yīmene mō te aliki;
\q1 ko toku alelo nei kaina loa te pēni a te kovi na mākalo e te tuti.
'''
    usxdoc = readFile(usfm, informat="usfm")
    refs = RefList("GEN 1; PSA 44-45")
    subdoc = usxdoc.getrefs(*refs)
    f = subdoc.outUsfm(None)
    if "\\d" not in f:
        fail(f"Missing \\d in {f}")

