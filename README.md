# USFMTC Module

## Introduction

The USFMTC module is a module for reading and writing [USFM](docs.usfm.bible) scripture files in
all their formats: USFM, USX and USJ. It is designed to be a reference
implementation of the standard. It also has support for Scripture References.

```
import sys, usfmtc
from usfmtc.versification import cached_versification
from usfmtc.reference import Ref, RefList

engvrs = cached_versification("eng")   # can also be a path to a .vrs file
usxdoc = usfmtc.readFile(sys.argv[1])
usxdoc.canonicalise()
# usxdoc.reversify(engvrs, None)
usxdoc.saveAs(sys.argv[2])

r = Ref("ISA 9:1-4")      # returns a RefRange
canr = engvrs.remap(r, None)    # one way conversion
print(canr)     # prints "ISA 8:23-9:3"
rlist = RefList("JHN 3:16, GEN 1:1, PSA 23, ISA 53, PSA 23:1")
print(rlist.simplify())     # GEN 1:1; PSA 23; ISA 53; JHN 3:16
print(Ref("PSA 23").end())  # PSA 23:6
print(Ref("PSA 23:10").isvalid())   # False

newdoc = usxdoc.getrefs(Ref("PSA 23:2-4"))
print(newdoc.outUsfm(None))     # A new doc of just PSA 23:2-4
```

The internal representation of the data is as an ElementTree structure
conforming to the USX standard.

See the tests/test_\*.py files for more examples. See also pydoc usfmtc.

## Utilities

usfmtc comes with a few utilities:

- usfmconv. Converts from one serialisation to another
- usfmreversify. Change the versification of a file to something different

