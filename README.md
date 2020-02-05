hg-export-tool
=====================

This is a short script to run `hg-fast-export` on a list of mercurial repositories to
convert them to git repositories. It is pretty simple, it just automates the process of
running `hg-fast-export.sh` on a potentially large number of repositories. If there are
anonymous heads, it first adds a commit to give them a unique branch name by appending
`-anonymous-<n>` to their existing branch names, with n a unique integer. If such a head
has a bookmark, the bookmark name will be used instead. This ensures these heads survive
the conversion to git

This script uses Python 2 because `hg-fast-export` is Python 2 only at present.

run it as `python2 exporter.py REPO_MAPPING_FILE [args ...]`

where `REPO MAPPING FILE` is the path to a file containing JSON mapping filepaths of
mercurial repositories to a desired filepaths of the resulting git repositories. The git
repositories must not already exist.

All remaining arguments will be passed to invocations of `hg-fast-export.sh`. One
argument you will probably want to use is `-A` to pass an author map file. To get a list
of authors present in the mercurial commits, run the `list-authors.py` script as
`python2 list-authors.py REPO_MAPPING_FILE`. This will output a file `authors.map` in
the correct format for passing to `hg-fast-export.sh` with the `-A` argument. You can
modify this file to fill in the desired git commit names and emails by editing on the
right side of the equals sign on each line, otherwise `<devnull@localhost>` will be used
for all unknown email addresses (the default behaviour of `hg-fast-export`)

On Windows, you will need to run the script from within a 'git bash' shell or whatever
git comes with on Windows, so that bash exists, which `hg-fast-export` uses.

This script will, for each mercurial repo in the `REPO_MAPPING_FILE`:

1. Make a temporary copy of the mercurial repository
2. When a branch has more than one head, make empty branch commits such that each extra
   head has a child commit with a unique branch name
1. ensure the destination git repository directory exists
2. run `git init` in in the destination repository
2. `cd` to the destination git repository directory
3. Run `hg-fast-export.sh -r <hg_repo_path> [args ...]`, passing all  arguments that
   were passed  to 
4. run `git reset --hard master` to put the git repository into a clean state.


FAQ
===

Q. Doesn't functionality like this properly belong in `hg-fast-export`?
A. Yes, but I'm in a hurry to get this stuff working to port my own repositories, and
   it's easier to wrap `hg-fast-export` than to understand it well enough to modify it.

TODO:

List heads.

If they have non-unique names, number them by date, newest gets the lowest number. Or,
if they have bookmarks at them, use that.


