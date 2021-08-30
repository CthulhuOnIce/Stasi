# DELETE BEFORE MERGING PR

import os
import sys
import subprocess

print(sys.executable)

print(os.spawnlp(os.P_NOWAIT, sys.executable, "main.py"))
print("ok")

input()