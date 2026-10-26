import os, shutil
import pytest
from usfmtc.ptsettings import ParatextSettings

testdir = os.path.dirname(__file__)

def _settings(**kw):
    vals = {"Name": "TST", "LanguageIsoCode": "en:::", "Versification": "4",
            "FileNameBookNameForm": "41MAT", "FileNamePrePart": "", "FileNamePostPart": "TST.usfm"}
    vals.update(kw)
    return "<ScriptureText>\n" + "".join(f"  <{k}>{v}</{k}>\n" for k, v in vals.items() if v is not None) \
            + "</ScriptureText>\n"

def _project(path, booknames=True, bkfile="32JONTST.usfm", **kw):
    """ A project directory holding Jonah """
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "Settings.xml"), "w", encoding="utf-8") as outf:
        outf.write(_settings(**kw))
    shutil.copy(os.path.join(testdir, "32JONBSB.usfm"), os.path.join(path, bkfile))
    if booknames:
        shutil.copy(os.path.join(testdir, "BookNames.xml"), os.path.join(path, "BookNames.xml"))
    return path

def test_settings(tmp_path):
    s = ParatextSettings(_project(str(tmp_path / "TST")))
    assert s['Name'] == "TST"
    assert s.langid == "en"
    assert s.getBookFilename("JON") == "32JONTST.usfm"
    assert s.getBookFilename("MAT") == "41MATTST.usfm"
    assert s.getBookPath("MAT") is None
    assert s.bookmap == {"JON": "32JONTST.usfm"}
    assert s['BooksPresent'].index("1") == 31 and s['BooksPresent'].count("1") == 1
    assert s.getABook() == "JON" and s.getABook("JON") is None

def test_langid(tmp_path):
    s = ParatextSettings(_project(str(tmp_path / "TST"), LanguageIsoCode="wsg:Latn::"))
    assert s.langid == "wsg-Latn"

def test_infer_naming(tmp_path):
    """ Settings.xml without the naming, which is worked out from the files """
    s = ParatextSettings(_project(str(tmp_path / "TST"), bkfile="32JONxyz.SFM", FileNameBookNameForm=None,
                                  FileNamePrePart=None, FileNamePostPart=None))
    assert s.getBookFilename("JON") == "32JONxyz.SFM"
    assert s.getBookFilename("MAT") == "41MATxyz.SFM"

def test_versification(tmp_path):
    prj = _project(str(tmp_path / "TST"))
    s = ParatextSettings(prj)
    assert s.vrsname == "eng" and s.versification is None
    assert len(s.getVersification()["JON"]) == 5           # 4 chapters
    with open(os.path.join(prj, "custom.vrs"), "w") as outf:
        outf.write("JON 1:17 2:10 3:10 4:11 5:3\n")
    s = ParatextSettings(prj)
    assert s.versification == "custom.vrs"
    assert len(s.getVersification()["JON"]) == 6
    assert len(s.getVersification()["GEN"]) == 51           # the rest is still eng
    assert ParatextSettings(_project(str(tmp_path / "T2"), Versification="0")).getVersification() is None

def test_booknames(tmp_path):
    s = ParatextSettings(_project(str(tmp_path / "TST")))
    assert s.hasLocalBookNames
    assert s.booknames.localbook("JON", 2) == "The Book of Jonah"
    env = s.getRefEnvironment()
    assert env.localbook("JON", 0) == "Jon"
    assert s.getRefEnvironment() is env

def test_refenv_separators(tmp_path):
    s = ParatextSettings(_project(str(tmp_path / "TST"), ChapterVerseSeparator=".|:",
                                  NoSpaceBetweenBookAndChapter="True"))
    env = s.getRefEnvironment()
    assert env.cvsep == "." and env.bookspace == ""

def test_ldml(tmp_path):
    prj = _project(str(tmp_path / "TST"))
    with open(os.path.join(prj, "en.ldml"), "w") as outf:
        outf.write("<ldml><layout><orientation><characterOrder>left-to-right</characterOrder>"
                   "</orientation></layout></ldml>")
    s = ParatextSettings(prj)
    assert s.find_ldml("layout/orientation/characterOrder").text == "left-to-right"
    assert ParatextSettings(_project(str(tmp_path / "T2"))).find_ldml("layout") is None
