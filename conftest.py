import os
import sys

_root = os.path.dirname(__file__)
if _root not in sys.path:
    sys.path.insert(0, _root)

_tools = os.path.join(_root, "tools")
if os.path.isdir(_tools):
    for _entry in os.listdir(_tools):
        _path = os.path.join(_tools, _entry)
        if os.path.isdir(_path) and _path not in sys.path:
            sys.path.insert(0, _path)
