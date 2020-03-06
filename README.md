hg-export-tool
=====================

This is a script to run [`hg-fast-export`](https://github.com/frej/fast-export/) on a
list of mercurial repositories to convert them to git repositories. If there are
multiple heads in the same branch, it first converts each to a uniquely-named branch, by
amending the commit at each head to add a branch name. This conversion is done with a
temporary copy of the repository; the original repository is left unmodified.

The branch names used are of the form `<existing_branch_name>-<n>` with n an
incrementing integer starting from 1. If such a head has a bookmark, the bookmark name
will be used instead. This ensures these heads survive the conversion to git.

![hg_screenshot.png](example/hg_screenshot.png)\
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⬇\
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⬇\
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⬇\
![git_screenshot.png](example/git_screenshot.png)


Why
===

Q. What's wrong with github's mercurial import?

A. It doesn't import bookmarked/anonymous heads, and it gets the order of parents of
   merge commits wrong randomly, resulting in an incorrect concept of which branch was
   merged into which, causing less-than-useful commit graphs and incorrect diffs for
   merge commits. The former issue is by design, and I reported the latter issue to
   github but did not get a response.

Q. Doesn't functionality like this properly belong in `hg-fast-export`?

A. Yes, but I'm in a hurry to get this stuff working to port my own repositories, and
   it's easier to wrap `hg-fast-export` than to understand it well enough to modify it.

Q. It's pretty disappointing that BitBucket dropped mercurial support without providing
   any migration tools, isn't it? Would you recommend avoiding doing business with
   Atlassian in the future?

A. Yes and yes.


Requirements
============

To use this tool, you'll need Python 2.7 or 3.5+ with the `mercurial` module installed.
You will also need the `git` and `hg` commands to be in your path, such that they
function from the command line. On Windows, you will need to install [Git for
Windows](https://git-scm.com/download/win) in order to have git bash, which is needed by
`hg-fast-export`.

To install mercurial, run: `pip install mercurial`, or use your system's package manager
to install the mercurial libraries for the version of Python you are using.

To get this script, clone or download this repository.


Usage
=======

Run this script as:
```bash
python exporter.py [--bash=<path-to-git-bash-on-windows>] REPO_MAPPING_FILE [args ...]
```

where `REPO MAPPING FILE` is the path to a file containing JSON mapping filepaths of
mercurial repositories to the desired filepaths of the resulting git repositories, for
example:

```json
{
    "example.hg": "example.git",
    "/some/other/repo.hg": "/some/other/repo.git"
}
```

If the git already exist for a given mapping, that conversion will be skipped. Delete
the git repository and run the tool again to redo the conversion.If the filepaths in
this file are relative paths, they will be interpreted relative to the directory
containing the repo mapping file.

All remaining arguments will be passed to invocations of `hg-fast-export.sh`.

One argument you will probably want to use is `-A` to pass an author map file. To get a
list of authors present in the mercurial commits, run the `list-authors.py` script as
`python list-authors.py REPO_MAPPING_FILE`. This will output a file `authors.map` in
the same directory as the repo mapping file, in the correct format for passing to
`hg-fast-export.sh` with the `-A` argument, e.g:
```bash
python exporter.py /some/path/repo_mapping.json -A /some/path/authors.map 
```
You can modify this file to fill in the desired git commit names and emails by editing
on the right side of the equals sign on each line, otherwise `<devnull@localhost>` will
be used for all unknown email addresses (the default behaviour of `hg-fast-export`).

Another argument you will likely want to pass is `--hg-hash`. This will add git notes to
all converted commits, with the hg commit hash of the commit they came from. These notes
are in the `hg` namespace, and can be shown with `git log` like:
```bash
$ git log --show-notes=hg
commit 6e77576102b52186b77b3a43b272a20179097839 (HEAD -> master)
Merge: 3324003 896fd1f
Author: chrisjbillington <chrisjbillington@gmail.com>
Date:   Thu Feb 6 10:18:31 2020 -0500

    Merge with feature

Notes (hg):
    169d1e2800cba83bef09e17f6d01c07dc5b7371b

commit 896fd1f405a4e3797c5d136627386ad49add36f8 (feature)
Author: chrisjbillington <chrisjbillington@gmail.com>
Date:   Thu Feb 6 10:18:12 2020 -0500

    Close feature branch

Notes (hg):
    74d0d6173c2367e51c5d12f2bb54c39a545c8975

...

```

Or you can get the hg hash of a single git commit by showing a single note:
```bash
$ git notes --ref hg show HEAD
169d1e2800cba83bef09e17f6d01c07dc5b7371b
```

If you push the repo somewhere, don't forget to push the notes:
```bash
$ git push origin refs/notes/*
```

Notes are not included in clones by default, to fetch them into a new clone do:
```bash
$ git fetch origin refs/notes/*:refs/notes/*
```

This repository also includes a script `list-branches-differing-by-case.py`. Run it as:
`python list-branches-differing-by-case.py REPO_MAPPING_FILE` to see a list of branch
names of each repository that differ only by case. To rename these branches, you may use
a branch mapping file containing lines in the format `"OrigBranchName"="newbranchname"`,
and pass it to `hg-fast-export` with the argument: `-B branches.map`. If you need to do
different branch mappings for different repos, you'll have to split your repo
mapping file up and run `export.py` multiple times, sorry.

Windows
=======
On Windows, you will need to tell the script the path to git bash so that it may run
`hg-fast-export` using it, for example:

```bash
python exporter.py --bash="C:\Program Files\Git\bin\bash.exe" some/path/repo_mapping.json [args ...]`
```

Where the path is the location of git bash on your system. On Unix you can omit that
argument.


What it does
============
This script will, for each mercurial repo in the `REPO_MAPPING_FILE`:

1. Make a temporary copy of the mercurial repository
2. When a branch has more than one head, amend the head commits of that branch to give
   them unique branch names
3. ensure the destination git repository directory exists
4. run `git init` in in the destination repository
5. Run `git config core.ignoreCase false` to set git case-sensitive for the repo (this
   is required for `hg-fast-export` to not raise an error on Windows)
5. `cd` to the destination git repository directory
6. Run `hg-fast-export.sh -r <hg_repo_path> [args ...]`, passing all the additional
   arguments that were passed  to `exporter.py`
7. run `git checkout master` to put the git repository into a clean state
8. If `--hg-hashes` was given, update the git notes to contain the hashes of the
   original mercurial anonymous/bookmarked heads before any  were amended.


Example
=======

An example is included in this repository, of a mercurial repository
`example/example.hg`, which looks like this in `tortoisehg`:

![hg_screenshot.png](example/hg_screenshot.png)

There is a repo mapping file `example/repo_mapping.json` with
the following contents:
```json
{
    "example.hg": "example.git"
}
```

Note: Due to git checking out files with platform-specific line-endings, when cloning
this repository on Windows, the example mercurial repository appears as having
uncommitted changes. Revert them before continuing, as mercurial with otherwise refuse
to operate on this repository:
```bash
hg update -C -R example/example.hg
```

First we create an author mapping file:
```bash
python list-authors.py example/repo_mapping.json
```

This outputs a file `example/authors.map` containing the following:
```
"chrisjbillington"="chrisjbillington <devnull@localhost>"
```
Which we might edit to change `devnull@localhost` to an actual email address, before
running:
```bash
python exporter.py example/repo_mapping.json -A example/authors.map --hg-hash
```

And our new git repository has been created at `example/example.git`, which looks
like the following in Sublime merge:

![git_screenshot.png](example/git_screenshot.png)
