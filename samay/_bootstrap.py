#!/usr/bin/env python3
# Bootstrap: prepend system gi package dir so GTK3 imports work within this venv.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/lib/python3/dist-packages")
# Also: add vendor dir for requests/pytz/dateutil so app code can import them directly.
sys.path.insert(0, os.path.join(HERE, "vendor"))
