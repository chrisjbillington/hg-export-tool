import subprocess
import json
import sys
import os
import errno
from binascii import hexlify
from tempfile import gettempdir
import shutil
from contextlib import contextmanager
from collections import defaultdict
import itertools

here = os.path.dirname(os.path.abspath(__file__))
FAST_EXPORT = os.path.abspath(os.path.join(here, 'fast-export', 'hg-fast-export.sh'))
if not os.path.exists(FAST_EXPORT):
    print(
        "%s does not exist. " % FAST_EXPORT
        + "Please read README.md for instructions on obtaining hg-fast-export."
    )
    sys.exit(1)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

@contextmanager
def switch_directory(directory):
    """Context manager to chdir to a directory temporarily"""
    cwd = os.getcwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(cwd)

def init_git_repo(git_repo):
    if os.path.exists(git_repo):
        print(
            "repo {} already exists, please delete it and run this script again".format(
                git_repo
            )
        )
        sys.exit(1)
    mkdir_p(git_repo)
    subprocess.check_call(['git', 'init', git_repo])

def copy_hg_repo(hg_repo):
    random_hex = hexlify(os.urandom(16))
    hg_repo_copy = os.path.join(
        gettempdir(), os.path.basename(hg_repo) + '-' + random_hex
    )
    shutil.copytree(hg_repo, hg_repo_copy)
    return hg_repo_copy

def get_heads(hg_repo):
    """Return alist of topological heads, including of closed branches, each in the
    format:

    {
        'commit_hash': '<hash>',
        'branch': '<branchname>',
        'bookmark': '<bookmark name or None>',
        'timstamp': '<utc_unix_timestamp>',
    }

    """

    cmd = ['hg', 'heads', '--closed', '--topo', '--template', 'json']
    results = []
    with switch_directory(hg_repo):
        output = subprocess.check_output(cmd)
    heads = json.loads(output)
    for head in heads:
        results.append(
            {
                'hash': head['node'],
                'branch': head['branch'],
                'timestamp': head['date'][0] + head['date'][1],  # add UTC offset
                # If multiple bookmarks, ignore all but one:
                'bookmark': head['bookmarks'][0] if head['bookmarks'] else None,
            }
        )

    return results

def fix_branches(hg_repo):
    all_heads = get_heads(hg_repo)
    heads_by_branch = defaultdict(list)
    # Group by branch:
    for head in all_heads:
        heads_by_branch[head['branch']].append(head)
    # Sort by timestamp, newest first:
    for heads in heads_by_branch.values():
        heads.sort(reverse=True, key=lambda head: head['timestamp'])
    # Iterate over additional heads of each branch, skipping over the most recently
    # commited to:
    for branch, heads in heads_by_branch.items():
        counter = itertools.count(1)
        for head in heads[1:]:
            if head['bookmark'] is not None:
                new_branch_name = head['bookmark']
            else:
                new_branch_name = branch + '-anonymous-%d' % counter.next()
            # Make a new commit with the new branch name:
            with switch_directory(hg_repo):
                subprocess.check_call(['hg', 'up', head['hash']])
                subprocess.check_call(['hg', 'branch', new_branch_name])
                subprocess.check_call(
                    [
                        'hg',
                        'commit',
                        '-u',
                        'hg-export-tool',
                        '-m',
                        'Convert anonymous head/bookmark to named branch',
                    ]
                )

def convert(hg_repo_copy, git_repo, fast_export_args):
    with switch_directory(git_repo):
        subprocess.check_call(
            [FAST_EXPORT, '-r', hg_repo_copy]
            + fast_export_args
        )
        subprocess.check_call(['git', 'reset', '--hard', 'master'])

def process_repo(hg_repo, git_repo, fast_export_args):
    init_git_repo(git_repo)
    hg_repo_copy = copy_hg_repo(hg_repo)
    try:
        fix_branches(hg_repo_copy)
        convert(hg_repo_copy, git_repo, fast_export_args)
    finally:
        shutil.rmtree(hg_repo_copy)

def main():
    try:
        REPO_MAPPING_FILE = sys.argv[1]
    except IndexError:
        print("Error: no REPO_MAPPING_FILE passed as command line argument")
        sys.exit(1)

    fast_export_args = sys.argv[1:]

    REPO_MAPPING_FILE = os.path.abspath(REPO_MAPPING_FILE)
    basedir = os.path.dirname(REPO_MAPPING_FILE)

    with open(REPO_MAPPING_FILE) as f:
        repo_mapping = json.load(f)

    for i, arg in enumerate(fast_export_args):
        # Quick and dirty, if any args are filepaths, convert to absolute paths:
        if os.path.exists(arg):
            fast_export_args[i] = os.path.abspath(arg)

    for hg_repo, git_repo in repo_mapping.items():
        process_repo(
            # Interpret the paths as relative to basedir - will do nothing if they were
            # already absolute paths:
            os.path.join(basedir, hg_repo),
            os.path.join(basedir, git_repo),
            fast_export_args,
        )

if __name__ == '__main__':
    main()