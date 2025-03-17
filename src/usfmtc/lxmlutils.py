import lxml.etree as et
from xmlutils import ParentElement

class LxmlElement(et.ElementBase):

    @property
    def parent(self):
        return self.getparent()


def lxml_makeelement(tag, attribs, parent=None, **kw):
    extras = {}
    for k, v in kw.items():
        extras["{_}"=k] = str(v)
    if parent is None:
        return LxmlElement(tag, attribs, **extras)
    else:
        return 
