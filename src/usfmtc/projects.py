""" Paratext projects, and the directories of projects that hold them. These are
    base classes that applications (e.g. ptxprint) subclass to add their own extras. """

import os, logging
from usfmtc.ptsettings import ParatextSettings
from usfmtc.usfm import UsfmCollection

logger = logging.getLogger(__name__)


class Project:
    """ A Paratext project directory, whose settings and books are read when first used """

    settingsclass = ParatextSettings
    collectionclass = UsfmCollection

    def __init__(self, prjid, path, guid=None):
        self.prjid = prjid
        self.path = path
        self.guid = guid
        self._settings = None
        self._books = None
        self._refenv = None

    def __repr__(self):
        return f"{self.prjid} {self.path}"

    @property
    def settings(self):
        if self._settings is None:
            self._settings = self.settingsclass(self.path)
        return self._settings

    @property
    def books(self):
        if self._books is None:
            self._books = self.collectionclass(self.settings.getBookPath, self.path)
        return self._books

    @property
    def lang(self):
        return self.settings.langid

    @property
    def booknames(self):
        """ The project's book names: BookNames.xml, else the books' \\toc entries """
        if self.settings.hasLocalBookNames:
            return self.settings.booknames
        return self.books.makeBookNames()

    @property
    def refenv(self):
        """ The reference environment: the book names with the project's separators """
        if self._refenv is None:
            if self.settings.hasLocalBookNames:
                self._refenv = self.settings.getRefEnvironment()
            else:
                self._refenv = self.settings.getRefEnvironment(self.booknames)
        return self._refenv


class Projects:
    """ The projects in one or more project tree directories, found by name """

    projectclass = Project

    def __init__(self, *treedirs):
        self.treedirs = []
        self.projects = {}          # lower cased prjid -> Project
        for t in treedirs:
            self.addTreedir(t)

    def __len__(self):
        return len(self.projects)

    def addTreedir(self, path):
        """ Adds each subdirectory that has Paratext settings, named by its directory name """
        path = os.path.abspath(path)
        if path in self.treedirs:
            return False
        try:
            sdir = sorted(os.listdir(path))
        except FileNotFoundError:
            return False
        self.treedirs.append(path)
        for d in sdir:
            p = os.path.join(path, d)
            if not os.path.isdir(p):
                continue
            if not any(os.path.exists(os.path.join(p, a)) for a in ParatextSettings.settingsfiles):
                continue
            self.addProject(d.split(".")[0], p)
        return True

    def addProject(self, prjid, path, guid=None):
        key = prjid.lower()
        if key in self.projects:
            if self.projects[key].path != path:
                logger.warning(f"Project {prjid} at {path} is hidden by {self.projects[key].path}")
            return self.projects[key]
        res = self.projects[key] = self.projectclass(prjid, path, guid)
        return res

    def findProject(self, prjid):
        if not prjid:
            return None
        return self.projects.get(prjid.lower(), None)

    def find(self, product):
        """ The project for a reference's product prefix, e.g. "en+BSB". For now only
            the product (the last part) is used: it is the project's directory name. """
        if not product:
            return None
        return self.findProject(product.split("+")[-1])
