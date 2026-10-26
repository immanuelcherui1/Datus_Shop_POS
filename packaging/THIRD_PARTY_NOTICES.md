# Third-party components

DATUS installer artifacts include third-party software under its original licenses:

- Python and its standard library: Python Software Foundation license.
- PostgreSQL: PostgreSQL license; bundled server and command-line notices are retained in `_internal/postgresql/server_license.txt` and `commandlinetools_3rd_party_licenses.txt`.
- Tcl/Tk: Tcl/Tk license notices distributed with the official CPython binary dependencies; retained in the corresponding script-library directories.
- NSIS installer runtime: NSIS licenses (including zlib/libpng and the compression module's license), retained with the build notices.
- Python application libraries: original license files from installed distribution metadata.
- React, React DOM, Lucide and Tailwind: their original package licenses are retained with the frontend notices.

The build gathers the license files shipped with the installed Python distributions and the frontend production/build packages into the application bundle. These notices do not replace any component's original terms and do not grant a separate license to DATUS business code.

Component sources and licenses:

- https://www.python.org/psf/license/
- https://www.postgresql.org/about/licence/
- https://github.com/python/cpython-bin-deps
- https://nsis.sourceforge.io/Docs/AppendixI.html
