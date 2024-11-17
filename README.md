# `similar-images`

This is a tool to determine similar images and deduplicate them based on
criteria most bytes, most pixes or by default both.

Workflow, e.g.:

```shell
# Create /tmp/dups with a separate directory for each group of similar images
# so you can verify similarity e.g. with `gwenview`
$ similar-images preview -p /tmp/dups /some/path1 /some/path2

# Show which actions are recommended if we want to keep those images with the
# largest file sizes.
$ similar-images show --keep-by=most-bytes /some/path1 /some/path2

# After reviewing the output of `show`, run dedup to perform the actions
$ similar-images dedup --keep-by=most-bytes /some/path1 /some/path2
```

# Installation

Requires Python 3.12 (for `pathlib`'s `relative_to(walk_up = False)`)

```shell
$ mkdir venv
$ python3 -m venv venv
$ ./venv/bin/pip3 install .
$ ./venv/bin/similar-images --help
```

(For Nix-OS, that is:)
```shell
$ nix shell github:GuillaumeDesforges/fix-python nixpkgs#python312
$ python3 -m venv venv --copies
$ ./venv/bin/pip3 install .
$ fix-python --venv venv
```

## Usage

The top-level command:

```shell
$ similar-images --help
usage: similar-images [-h] [--app-cache-dir APP_CACHE_DIR] {preview,show,dedup} ...

Finds and removes similar images

positional arguments:
  {preview,show,dedup}
    preview             Show a preview of similar images
    show                Show what dedup actions can be taken
    dedup               Actually dedup and perform actions listed by "show"

options:
  -h, --help            show this help message and exit
  --app-cache-dir APP_CACHE_DIR
```

`preview`:

```shell
$ similar-images preview --help
usage: similar-images preview [-h] --preview-dir PREVIEW_DIR [--force] [--no-progress-bar] dir [dir ...]

positional arguments:
  dir

options:
  -h, --help            show this help message and exit
  --preview-dir PREVIEW_DIR, -p PREVIEW_DIR
  --force, -f           Remove and recreate any existing --preview-dir. *Be careful*
  --no-progress-bar, -n
```

`show` and `dedup` have the same options:

```shell
$ /similar-images (show|dedup) --help   
usage: similar-images show [-h] [--keep-by {best,most-pixels,most-bytes,first}] [--name-by {keep-by,first}]
                           [--dups DUPS] [--no-progress-bar]
                           dir [dir ...]

positional arguments:
  dir

options:
  -h, --help            show this help message and exit
  --keep-by {best,most-pixels,most-bytes,first}
                        By default we keep the best image: with the biggest size and highest resolution. If these
                        are not the same, i.e. one image is the largest in bytes and the other has highest number
                        of bytes, a warning is shown and nothing is done.
  --name-by {keep-by,first}
                        Likely an obscure option. By default, we keep the biggest image as described under --keep-
                        by. --name-by=first will move the biggest image to replace the first image, keeping the
                        biggest file with the filename of the first image. This is handy if the first directory has
                        better order but lower quality photos.
  --dups DUPS           Which dup sets, as either the string "obvious" meaing all obvious sets, or comma-separated
                        numbers, to apply the action to. If not given, the action will apply to all dup sets. E.g.
                        "obvious" or "5,7,11".
  --no-progress-bar, -n
```

# Appendix

(Just so I don't forget myself)

On linux for viewing directories with images, `gwenview` or `digikam` can be
used. `digikam` is also excellent for re-ordering sequences and renaming images
sequences, to e.g. `image-001.jpg`, `image-002.jpg`, etc.