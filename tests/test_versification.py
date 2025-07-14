import pytest
from pytest import fail
from usfmtc import readFile
from usfmtc.reference import Ref
from usfmtc.versification import Versification, cached_versification
from usfmtc.usxmodel import etCmp
import os

engvrs = cached_versification("eng")
jon_usfm = readFile(os.path.join(os.path.dirname(__file__), "32JONBSB.usfm"))

def cmptest(intext, outtext, bk, chap, msg, vrsf=None, rev=False, **kw):
    prefix = r'''\id {} Test book
\c {}
'''.format(bk, chap)
    inu = readFile(prefix+intext, informat="usfm")
    outu = readFile(prefix+outtext, informat="usfm")
    print(inu.outUsfm())
    if rev:
        inu.reversify(None, vrsf or engvrs, **kw)
    else:
        inu.reversify(vrsf or engvrs, None, **kw)
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

def test_maprange():
    r = Ref("ISA 9:1-4")
    res = engvrs.remap(r, None)
    if str(res) != "ISA 8:23-9:3":
        fail(f"{r} remaps to {res} instead of ISA 8:23-9:3")

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
    if r.versification.name != "Original":
        fail(f"{r} versification is {r.versification.name}")

def test_hasvrs():
    r = Ref("ISA 64:1", versification=engvrs)
    if r.versification.name != "English":
        fail(f"{r} versification is {r.versification.name}")
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


def test_isa64():
    intext = r'''
\p
\v 17 ¶ O \nd LORD\nd*, why hast thou made us to err from thy ways, \add and\add* hardened our heart from thy fear? Return for thy servants’ sake, the tribes of thine inheritance.
\v 18 The people of thy holiness have possessed \add it\add* but a little while: our adversaries have trodden down thy sanctuary.
\v 19 We are \add thine:\add* thou never barest rule over them; they were not called by thy name.\f + \fr 63.19 \ft they…: Heb. thy name was not called upon
 them\f*
\c 64
\p
\v 1 Oh that thou wouldest rend the heavens, that thou wouldest come down, that the mountains might flow down at thy presence,
\v 2 As \add when\add* the melting fire burneth, the fire causeth the waters to boil, to make thy name known to thine adversaries, \add that\add* the nations may tremble at thy presence!\f + \fr 64.2 \ft the melting…: Heb. the fire of meltings\f*
\v 3 When thou didst terrible things \add which\add* we looked not for, thou camest down, the mountains flowed down at thy presence.
\v 4 For since the beginning of the world \add men\add* have not heard, nor perceived by the ear, neither hath the eye seen, O God, beside thee, \add what\add* he hath prepared for him that waiteth for him.\f + \fr 64.4 \ft seen…: or, seen a God beside thee, which doeth so for him, etc\f*
\v 5 Thou meetest him that rejoiceth and worketh righteousness, \add those that\add* remember thee in thy ways: behold, thou art wroth; for we have sinned: in those is continuance, and we shall be saved.
'''
    outtext = r'''
\p \v 17 ¶ O \nd LORD\nd*, why hast thou made us to err from thy ways, \add and\add* hardened our heart from thy fear? Return for thy servants’ sake, the tribes of thine inheritance.
\v 18 The people of thy holiness have possessed \add it\add* but a little while: our adversaries have trodden down thy sanctuary.
\v 19 We are \add thine:\add* thou never barest rule over them; they were not called by thy name.\f + \fr 63.19 \ft they…: Heb. thy name was not called upon
them\f*
\c 64
\p \v 1 Oh that thou wouldest rend the heavens, that thou wouldest come down, that the mountains might flow down at thy presence,
As \add when\add* the melting fire burneth, the fire causeth the waters to boil, to make thy name known to thine adversaries, \add that\add* the nations may tremble at thy presence!\f + \fr 64.2 \ft the melting…: Heb. the fire of meltings\f*
\v 2 When thou didst terrible things \add which\add* we looked not for, thou camest down, the mountains flowed down at thy presence.
\v 3 For since the beginning of the world \add men\add* have not heard, nor perceived by the ear, neither hath the eye seen, O God, beside thee, \add what\add* he hath prepared for him that waiteth for him.\f + \fr 64.4 \ft seen…: or, seen a God beside thee, which doeth so for him, etc\f*
\v 4 Thou meetest him that rejoiceth and worketh righteousness, \add those that\add* remember thee in thy ways: behold, thou art wroth; for we have sinned: in those is continuance, and we shall be saved.
'''
    cmptest(intext, outtext, 'ISA', 63, 'Merge verses in ISA 64')

def test_psa10():
    intext = r'''
\q1
\v 18 To judge the fatherless and the oppressed, that the man of the earth may no more oppress.\f + \fr 10.18 \ft oppress: or, terrify\f*
\c 11
\d To the chief Musician, \add A Psalm\add* of David.
\q1
\v 1 In the \nd LORD\nd* put I my trust: how say ye to my soul, Flee \add as\add* a bird to your mountain?
\q1
\v 2 For, lo, the wicked bend \add their\add* bow, they make ready their arrow upon the string, that they may privily shoot at the upright in heart.\f + \fr 11.2 \ft privily: Heb. in darkness\f*
'''
    outtext = r'''
\q1 \v 18 To judge the fatherless and the oppressed, that the man of the earth may no more oppress.\f + \fr 10.18 \ft oppress: or, terrify\f*
\c 11
\d To the chief Musician, \add A Psalm\add* of David.
\q1 \v 1 In the \nd LORD\nd* put I my trust: how say ye to my soul, Flee \add as\add* a bird to your mountain?
\q1 \v 2 For, lo, the wicked bend \add their\add* bow, they make ready their arrow upon the string, that they may privily shoot at the upright in heart.\f + \fr 11.2 \ft privily: Heb. in darkness\f*
'''
    cmptest(intext, outtext, 'PSA', 10, 'versetext headers after chapter')

def test_to0():
    vrsf = """PSA 51:0 = PSA 51:1
PSA 51:0 = PSA 51:2
"""
    v = Versification(vrsf)
    intext = r'''
\d To the chief Musician, A Psalm of David, when Nathan the prophet came unto him,
after he had gone in to Bath-sheba.
\q1 \v 1 Have mercy upon me, O God, according to thy lovingkindness:
according unto the multitude of thy tender mercies blot out my transgressions.
\q1 \v 2 Wash me throughly from mine iniquity, and cleanse me from my sin.
'''
    outtext = r'''
\d \v 1-2 \vp \vp* To the chief Musician, A Psalm of David, when Nathan the prophet came unto him,
after he had gone in to Bath-sheba.
\q1 \v 3 \vp 1\vp* Have mercy upon me, O God, according to thy lovingkindness:
according unto the multitude of thy tender mercies blot out my transgressions.
\q1 \v 4 \vp 2\vp* Wash me throughly from mine iniquity, and cleanse me from my sin.
'''
    cmptest(intext, outtext, 'PSA', 51, 'Reversification', keep=True)
