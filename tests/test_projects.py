import os, shutil
import pytest
from usfmtc.ptsettings import ParatextSettings
from usfmtc.usfm import UsfmCollection
from usfmtc.projects import Projects

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

def test_collection(tmp_path):
    prj = _project(str(tmp_path / "TST"))
    s = ParatextSettings(prj)
    books = UsfmCollection(s.getBookPath, prj)
    jon = books.getusx("JON")
    assert jon.book == "JON"
    assert books.getusx("JON") is jon
    assert books.get("MAT") is None
    books.clear("JON")
    assert books.getusx("JON") is not jon

def test_collection_readbook(tmp_path):
    """ Subclasses can wrap what is read """
    class Wrapped(UsfmCollection):
        def readbook(self, bk, bkfile):
            return ("wrapped", super().readbook(bk, bkfile))
        def getusx(self, bk):
            return self.get(bk)[1]
    prj = _project(str(tmp_path / "TST"))
    books = Wrapped(ParatextSettings(prj).getBookPath, prj)
    assert books.get("JON")[0] == "wrapped"
    assert books.getusx("JON").book == "JON"

def test_booknames_from_toc(tmp_path):
    prj = _project(str(tmp_path / "TST"), booknames=False)
    s = ParatextSettings(prj)
    assert not s.hasLocalBookNames
    names = UsfmCollection(s.getBookPath, prj).makeBookNames()
    assert names.localbook("JON", 2) == "Jonah"
    assert names.localbook("MAT", 2) == "MAT"

def test_projects(tmp_path):
    _project(str(tmp_path / "TST"))
    _project(str(tmp_path / "Other.bak"), booknames=False, LanguageIsoCode="fr:::")
    os.makedirs(tmp_path / "notaproject")
    pl = Projects(str(tmp_path))
    assert len(pl) == 2
    p = pl.find("TST")
    assert p.prjid == "TST" and p.lang == "en"
    assert pl.find("en+tst") is p
    assert pl.find("fr+TST") is p           # the language isn't checked yet
    assert pl.find("Other").lang == "fr"
    assert pl.find("Other").booknames.localbook("JON", 2) == "Jonah"
    assert p.booknames.localbook("JON", 2) == "The Book of Jonah"
    assert p.books.getusx("JON").book == "JON"
    assert pl.find("XYZ") is None and pl.find(None) is None
    assert not pl.addTreedir(str(tmp_path))

def test_project_refenv(tmp_path):
    """ The reference environment uses BookNames.xml, else \\toc, with the project's separators """
    _project(str(tmp_path / "TST"), ChapterVerseSeparator=".")
    _project(str(tmp_path / "NOBN"), booknames=False, ChapterVerseSeparator=".")
    pl = Projects(str(tmp_path))
    env = pl.find("TST").refenv
    assert env.localbook("JON", 2) == "The Book of Jonah" and env.cvsep == "."
    assert pl.find("TST").refenv is env
    env = pl.find("NOBN").refenv
    assert env.localbook("JON", 2) == "Jonah" and env.cvsep == "."
