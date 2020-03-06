from __future__ import print_function

import subprocess
import json
import sys
import os

try:
    REPO_MAPPING_FILE = sys.argv[1]
except IndexError:
    print("Error: no REPO_MAPPING_FILE passed as command line argument")
    sys.exit(1)

REPO_MAPPING_FILE = os.path.abspath(REPO_MAPPING_FILE)
basedir = os.path.dirname(REPO_MAPPING_FILE)

with open(REPO_MAPPING_FILE) as f:
    repos = list(json.load(f))

for repo in repos:
    cmd = ['hg', 'branches', '--closed', '--template', '{branch}\n']
    output = subprocess.check_output(cmd, cwd=os.path.join(basedir, repo)).decode('utf8')
    branches = output.splitlines()
    lower = [b.lower() for b in branches]
    problematic = [b for b in branches if lower.count(b.lower()) > 1]
    if problematic:
        print("Problematic branch names in", repo)
        for name in sorted(problematic):
            print(' ', name)
