import os
from pathlib import Path

runtime = Path(os.environ['DATUS_TCLTK_DIR'])
datas = [(str(runtime / 'lib/tcl8.6'), '_tcl_data'),
         (str(runtime / 'lib/tk8.6'), '_tk_data'),
         (str(runtime / 'lib/tcl8'), 'tcl8')]
binaries = [(str(runtime / 'bin/tcl86t.dll'), '.'), (str(runtime / 'bin/tk86t.dll'), '.')]
