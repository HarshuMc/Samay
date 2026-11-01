# -*- coding: utf-8 -*-
"""
SAMAY — Galaxy Watch / OneUI-style desktop clock for Debian 13 LXQt.
Run as:  python3 -m samay
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, os.path.join(HERE, "vendor"))

from app import main

if __name__ == "__main__":
    sys.exit(main())
