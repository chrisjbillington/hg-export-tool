import subprocess
import json
import sys
import os
import errno
from binascii import hexlify
from tempfile import gettempdir
import shutil
from collections import defaultdict
import itertools
import stat

here = os.path.dirname(os.path.abspath(__file__))
FAST_EXPORT_DIR = os.path.join(here, 'fast-export')

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def remove_readonly(func, path, _):
    """Clear the readonly bit and reattempt the removal. Necessary to delete read-only
    files in Windows, and the .git directory appears to contain such files."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def init_git_repo(git_repo):
    """Make a new git repo in a temporary directory, and return its path"""
    random_hex = hexlify(os.urandom(16)).decode()
    temp_repo = os.path.join(
        gettempdir(), os.path.basename(git_repo) + '-' + random_hex
    )
    mkdir_p(temp_repo)
    subprocess.check_call(['git', 'init', temp_repo])
    subprocess.check_call(['git', 'config', 'core.ignoreCase', 'false'], cwd=temp_repo)
    return temp_repo

def copy_hg_repo(hg_repo):
    random_hex = hexlify(os.urandom(16)).decode()
    hg_repo_copy = os.path.join(
        gettempdir(), os.path.basename(hg_repo) + '-' + random_hex
    )
    shutil.copytree(hg_repo, hg_repo_copy)
    return hg_repo_copy

def get_heads(hg_repo):
    """Return alist of heads, including of closed branches, each in the
    format:

    {
        'commit_hash': '<hash>',
        'branch': '<branchname>',
        'bookmark': '<bookmark name or None>',
        'timstamp': <utc_unix_timestamp>,
        'topological': <whether the head is a topological head>,
    }

    """

    cmd = ['hg', 'heads', '--closed', '--topo', '--template', 'json']
    output = subprocess.check_output(cmd, cwd=hg_repo)
    topo_heads = json.loads(output.decode('utf8'))

    cmd = ['hg', 'heads', '--closed', '--template', 'json']
    output = subprocess.check_output(cmd, cwd=hg_repo)
    all_heads = json.loads(output.decode('utf8'))

    results = []
    for head in all_heads:
        results.append(
            {
                'hash': head['node'],
                'branch': head['branch'],
                'timestamp': head['date'][0] + head['date'][1],  # add UTC offset
                # If multiple bookmarks, ignore all but one:
                'bookmark': head['bookmarks'][0] if head['bookmarks'] else None,
                'topological': head in topo_heads
            }
        )

    return results

def fix_branches(hg_repo):
    """Amend anonymous/bookmarked additional heads on a branch to be on a new branch ,
    either <branchname>-<n>, or the first bookmark name. Return a dict of commits
    amended mapping the original commit hash to the amended one"""
    all_heads = get_heads(hg_repo)
    heads_by_branch = defaultdict(list)
    # Group by branch:
    for head in all_heads:
        heads_by_branch[head['branch']].append(head)
    # Sort by timestamp, newest first:
    for heads in heads_by_branch.values():
        heads.sort(reverse=True, key=lambda head: head['timestamp'])
    amended_commits = {}
    for branch, heads in heads_by_branch.items():
        if len(heads) == 1 or all(not head['topological'] for head in heads):
            # No topological heads in this branch, no renaming:
            heads_to_rename = []
        elif all(head['topological'] for head in heads):
            # Only topological heads in this branch. Rename all but the most recently
            # committed to:
            heads_to_rename = heads[1:]
        else:
            # Topological and non-topological heads in this branch. Rename all
            # topological heads:
            heads_to_rename = [head for head in heads if head['topological']]
        counter = itertools.count(1)
        for head in heads_to_rename:
            if head['bookmark'] is not None:
                new_branch_name = head['bookmark']
            else:
                new_branch_name = branch + '-%d' % next(counter)
            # Amend the head to modify its branch name:
            subprocess.check_call(['hg', 'up', head['hash']], cwd=hg_repo)
            # Commit must be in draft phase to be able to amend it:
            subprocess.check_call(
                ['hg', 'phase', '--draft', '--force', head['hash']], cwd=hg_repo
            )
            subprocess.check_call(['hg', 'branch', new_branch_name], cwd=hg_repo)
            msg = subprocess.check_output(
                ['hg', 'log', '-r', head['hash'], '--template', '{desc}'], cwd=hg_repo
            ).rstrip(b'\n')
            subprocess.check_call(['hg', 'commit', '--amend', '-m', msg], cwd=hg_repo)
            new_hash = (
                subprocess.check_output(
                    ['hg', 'log', '-l', '1', '--template', '{node}\n'], cwd=hg_repo
                )
                .decode()
                .rstrip('\n')
            )
            amended_commits[head['hash']] = new_hash
    return amended_commits

def convert(hg_repo_copy, git_repo, fast_export_args, bash):
    env = os.environ.copy()
    env['PYTHON'] = sys.executable
    env['PATH'] = FAST_EXPORT_DIR + os.pathsep + env.get('PATH', '')
    env['HGENCODING'] = 'UTF-8'
    subprocess.check_call(
        [bash, 'hg-fast-export.sh', '-r', hg_repo_copy] + fast_export_args,
        env=env,
        cwd=git_repo,
    )
    subprocess.check_call(['git', 'checkout', 'master'], cwd=git_repo)

def update_notes(git_repo, amended_commits):
    """For commits that we amended on the hg side, update the git note for the
    corresponding commit to point to the original, unamended hg commit"""
    cmd = ['git', 'log', '--branches', '--show-notes=hg', '--format=format:%H %N']
    lines = subprocess.check_output(cmd, cwd=git_repo).decode('utf8').splitlines()
    # Mapping of amended hg hashes to git hashes, this is what is currently in the
    # notes:
    git_hashes = dict([line.strip().split()[::-1] for line in lines if line.strip()])
    for orig_hg_hash, amended_hg_hash in amended_commits.items():
        git_hash = git_hashes[amended_hg_hash]
        cmd = ['git', 'notes', '--ref', 'hg', 'remove', git_hash]
        subprocess.check_call(cmd, cwd=git_repo)
        cmd = ['git', 'notes', '--ref', 'hg', 'add', git_hash, '-m', orig_hg_hash]
        subprocess.check_call(cmd, cwd=git_repo)

def process_repo(hg_repo, git_repo, fast_export_args, bash):
    if os.path.exists(git_repo):
        msg = "git repo {} already exists, skipping.\n"
        sys.stderr.write(msg.format(git_repo))
        return
    temp_git_repo = init_git_repo(git_repo)
    hg_repo_copy = copy_hg_repo(hg_repo)
    try:
        amended_commits = fix_branches(hg_repo_copy)
        convert(hg_repo_copy, temp_git_repo, fast_export_args, bash)
        if amended_commits and '--hg-hash' in fast_export_args:
            update_notes(temp_git_repo, amended_commits)
        if '--hg-hash' in fast_export_args:
            verify_conversion(hg_repo, temp_git_repo)
        shutil.copytree(temp_git_repo, git_repo)
    finally:
        shutil.rmtree(temp_git_repo, onerror=remove_readonly)
        shutil.rmtree(hg_repo_copy, onerror=remove_readonly)


def list_of_hg_commits(hg_repo):
    cmd = ['hg', 'log', '--template', '{node}\n']
    return subprocess.check_output(cmd, cwd=hg_repo).decode('utf8').splitlines()


def get_commit_mapping(git_repo):
    """return a dict {git_hash: hg_hash} mapping git commit hashes to the corresponding
    mercurial hashes for a repo that has been converted using hg-fast-export with the
    --hg-hash option"""
    cmd = ['git', 'log', '--branches', '--show-notes=hg', '--format=format:%H %N']
    lines = subprocess.check_output(cmd, cwd=git_repo).decode('utf8').splitlines()
    return dict([line.strip().split() for line in lines if line.strip()])

def verify_conversion(hg_repo, git_repo):
    git_to_hg_hashes = get_commit_mapping(git_repo)
    hg_hashes = set(list_of_hg_commits(hg_repo))
    hashes_that_made_it = set(git_to_hg_hashes.values())
    try:
        assert hg_hashes == hashes_that_made_it
    except AssertionError:
        for hg_hash in hg_hashes - hashes_that_made_it:
            sys.stderr.write('hg hash %s has no corresponding git commit\n' % hg_hash)
        raise


def main():
    for i, arg in enumerate(sys.argv[:]):
        if arg.startswith('--bash'):
            del sys.argv[i]
            BASH = arg.split('=', 1)[1]
            break
    else:
        if os.name == 'nt':
            msg = "Missing --bash command line argument with path to git bash\n"
            sys.stderr.write(msg)
            sys.exit(1)
        BASH = '/bin/bash'
    try:
        REPO_MAPPING_FILE = sys.argv[1]
    except IndexError:
        msg = "Error: no REPO_MAPPING_FILE passed as command line argument\n"
        sys.stderr.write(msg)
        sys.exit(1)

    fast_export_args = sys.argv[2:]

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
            BASH
        )

if __name__ == '__main__':
    main()
