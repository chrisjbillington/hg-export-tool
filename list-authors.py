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

authors = set()
for repo in repos:
    repo = os.path.join(basedir, repo)
    cwd = os.getcwd()
    try:
        os.chdir(repo)
        output = subprocess.check_output(['hg', 'log', '--template', '{author}\n'])
        authors = authors.union(output.splitlines())
    finally:
        os.chdir(cwd)


authors_map = os.path.join(basedir, 'authors.map')
if os.path.exists(authors_map):
    print(
        "%s already exists. " % authors_map
        + "If you are sure you want to replace it, please "
        + "delete it and run this script again"
    )
    sys.exit(1)


with open(authors_map, 'w') as f:
    for author in authors:
        if '@' in author and ' <' in author:
            # Already a valid git author:
            git_author = author
        elif '@' in author:
            # Need to prepend a username, use the email prefix:
            git_author = author.strip('<>').split('@', 1)[0] + ' ' + author
        else:
            # Need to append an email address, use devnull@localhost:
            git_author = author + ' <devnull@localhost>'
        f.write('"{}"="{}"\n'.format(author, git_author))