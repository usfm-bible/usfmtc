import pytest
from pytest import fail
from usfmtc import readFile
from usfmtc.reference import Ref
from usfmtc.versification import Versification
from usfmtc.usxmodel import etCmp
import os

engvrs = Versification(os.path.join(os.path.dirname(__file__), "eng.vrs"))
jon_usfm = readFile(os.path.join(os.path.dirname(__file__), "32JONBSB.usfm"))

def cmptest(intext, outtext, bk, chap, msg):
    prefix = r'''\id {} Test book
\c {}
'''.format(bk, chap)
    inu = readFile(prefix+intext, informat="usfm")
    outu = readFile(prefix+outtext, informat="usfm")
    print(inu.outUsfm())
    inu.reversify(engvrs, None)
    print(inu.outUsfm())
    if not etCmp(inu.getroot(), outu.getroot(), verbose=True):
        fail(msg)

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
    # breakpoint()
    jtest.reversify(None, engvrs)
    print(jtest.outUsfm())
    if not etCmp(jtest.getroot(), jon_usfm.getroot(), verbose=True):
        fail(f"Unreversified text difference")

def test_engmap2():
    r = Ref("ISA 64:1")
    res = engvrs.remap(r, engvrs)
    if str(res) != "ISA 64:1":      # we don't want to delete it, delete v2 instead
        fail(f"{r} remaps to {res} instead of ISA 64:1")

def test_psa6():
    intext = r'''
\d To the chief Musician on Neginoth upon Sheminith, A Psalm of David.
\q1
\v 1 O \nd LORD\nd*, rebuke me not in thine anger, neither chasten me in thy hot displeasure.\f + \fr 6.1 \ft chief…: or, overseer\f*\f + \fr 6.1 \ft Sheminith: or, the eighth\f*
\q1
\v 2 Have mercy upon me, O \nd LORD\nd*; for I \add am\add* weak: O \nd LORD\nd*, heal me; for my bones are vexed.'''
    outtext = r'''
\d \v 1 To the chief Musician on Neginoth upon Sheminith, A Psalm of David.
\q1
\v 2 O \nd LORD\nd*, rebuke me not in thine anger, neither chasten me in thy hot displeasure.\f + \fr 6.1 \ft chief…: or, overseer\f*\f + \fr 6.1 \ft Sheminith: or, the eighth\f*
\q1
\v 3 Have mercy upon me, O \nd LORD\nd*; for I \add am\add* weak: O \nd LORD\nd*, heal me; for my bones are vexed.'''
    cmptest(intext, outtext, 'PSA', 6, 'Reorder for PSA 6')

def test_isa9():
    intext = r'''
\p
\v 19 ¶ And when they shall say unto you, Seek unto them that have familiar spirits, and unto wizards that peep, and that mutter: should not a people seek unto their God? for the living to the dead?
\v 20 To the law and to the testimony: if they speak not according to this word, \add it is\add* because \add there is\add* no light in
them.\f + \fr 8.20 \ft no…: Heb. no morning\f*
\v 21 And they shall pass through it, hardly bestead and hungry: and it shall come to pass, that when they shall be hungry, they shall fret themselves, and 
curse their king and their God, and look upward.
\v 22 And they shall look unto the earth; and behold trouble and darkness, dimness of anguish; and \add they shall be\add* driven to darkness.
\c 9
\p
\v 1 Nevertheless the dimness \add shall\add* not \add be\add* such as \add was\add* in her vexation, when at the first he lightly afflicted the land of Zebulun and the land of Naphtali, and afterward did more grievously afflict \add her by\add* the way of the sea, beyond Jordan, in Galilee of the
nations.\f + \fr 9.1 \ft of the nations: or, populous\f*
\v 2 The people that walked in darkness have seen a great light: they that dwell in the land of the shadow of death, upon them hath the light shined.
\v 3 Thou hast multiplied the nation, \add and\add* not increased the joy: they joy before thee according to the joy in harvest, \add and\add* as \add men\add* rejoice when they divide the spoil.\f + \fr 9.3 \ft not: or, to him\f*
\v 4 For thou hast broken the yoke of his burden, and the staff of his shoulder, the rod of his oppressor, as in the day of
Midian.\f + \fr 9.4 \ft For…: or, When thou brakest\f*'''
    outtext = r'''
\p \v 19 ¶ And when they shall say unto you, Seek unto them that have familiar spirits, and unto wizards that peep, and that mutter: should not a people seek unto their God? for the living to the dead?
\v 20 To the law and to the testimony: if they speak not according to this word, \add it is\add* because \add there is\add* no light in
them.\f + \fr 8.20 \ft no…: Heb. no morning\f*
\v 21 And they shall pass through it, hardly bestead and hungry: and it shall come to pass, that when they shall be hungry, they shall fret themselves, and
curse their king and their God, and look upward.
\v 22 And they shall look unto the earth; and behold trouble and darkness, dimness of anguish; and \add they shall be\add* driven to darkness.
\p \v 23 Nevertheless the dimness \add shall\add* not \add be\add* such as \add was\add* in her vexation, when at the first he lightly afflicted the land of Zebulun and the land of Naphtali, and afterward did more grievously afflict \add her by\add* the way of the sea, beyond Jordan, in Galilee of the
nations.\f + \fr 9.1 \ft of the nations: or, populous\f*
\c 9
\p \v 1 The people that walked in darkness have seen a great light: they that dwell in the land of the shadow of death, upon them hath the light shined.
\v 2 Thou hast multiplied the nation, \add and\add* not increased the joy: they joy before thee according to the joy in harvest, \add and\add* as \add men\add* rejoice when they divide the spoil.\f + \fr 9.3 \ft not: or, to him\f*
\v 3 For thou hast broken the yoke of his burden, and the staff of his shoulder, the rod of his oppressor, as in the day of
Midian.\f + \fr 9.4 \ft For…: or, When thou brakest\f*'''
    cmptest(intext, outtext, 'ISA', 8, 'Chapter shift for ISA 9')
