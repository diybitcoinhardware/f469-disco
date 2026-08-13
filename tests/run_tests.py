import sys
import unittest

curdir = sys.path[0]
pardir = curdir + "/.."
sys.path.append(pardir + "/libs/common")
sys.path.insert(1, pardir + "/libs/common/embit/src")
sys.path.append(pardir + "/libs/unix")
sys.path.append(pardir + "/usermods/udisplay_f469/display_unixport")

unittest.main("tests")
