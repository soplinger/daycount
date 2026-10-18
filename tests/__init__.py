import os
import sys

# Make the project root importable however the tests are launched
# (pytest, or python3 -m unittest discover -s tests -t .).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
