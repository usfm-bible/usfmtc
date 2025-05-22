# USFMTC Module

## Introduction

The USFMTC module is a module for reading and writing [USFM](docs.usfm.bible) scripture files in
all their formats: USFM, USX and USJ. It is designed to be a reference
implementation of the standard. It also has support for Scripture References.

```
import sys, usfmtc
from usfmtc.versification import Versification

# engvrs = Versification("eng.vrs")
usxdoc = usfmtc.readFile(sys.argv[1])
# usxdoc.canonicalise()
# usxdov.reversify(engvrs, None)
usxdoc.saveAs(sys.argv[2])
```

The internal representation of the data is as an ElementTree structure
conforming to the USX standard.

