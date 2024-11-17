import math
import shutil
from pathlib import Path

from . import image_processing


def format_str_for_counter(counter_max: int):
    return "%%0%dd" % (1 + int(math.log10(counter_max)))


def write_preview_dir(app_cache_dir: str, force: bool, ppreview,
                      src_paths: list[str], show_progress_bar: bool):
    if ppreview.is_dir():
        if force:
            shutil.rmtree(ppreview)
        else:
            raise ValueError(
                "%s already exists - please remove first" % ppreview)
    ppreview.mkdir()

    dups = image_processing.find_dups(
        app_cache_dir, src_paths, show_progress_bar)
    if len(dups) == 0:
        return

    dup_formatstr = "%%s-%s" % format_str_for_counter(len(dups))
    max_dups = max([len(d.paths) for d in dups])
    file_formatstr = "%s-%s-%%s%%s" % (format_str_for_counter(
        len(dups)), format_str_for_counter(max_dups))
    for i, dup in enumerate(dups):

        # rprint(i, dup)
        prefix = "obvious" if dup.is_obvious() else "unclear"
        dup_dir = ppreview / (dup_formatstr % (prefix, i+1))
        dup_dir.mkdir()
        for j, tuple in enumerate(dup.paths_with_evaluations()):
            f, evaluation = tuple
            fpath = Path(f)
            if fpath.is_absolute():
                src = fpath
            else:
                absolute = fpath.absolute()
                src = absolute.relative_to(dup_dir.resolve(), walk_up=True)
            dst = dup_dir / (file_formatstr %
                             (i+1, j+1, evaluation, fpath.suffix))
            dst.symlink_to(src)


def preview_func(args):
    ppreview = Path(args.preview_dir)
    write_preview_dir(args.app_cache_dir, args.force, ppreview,
                      args.dir, not (args.no_progress_bar))


def add_subparser(subparsers):
    parser = subparsers.add_parser(
        'preview', help='Show a preview of similar images')
    parser.add_argument('--preview-dir', '-p', type=str, required=True)
    parser.add_argument(
        '--force', '-f', action='store_true',
        help="Remove and recreate any existing --preview-dir. *Be careful*")
    parser.add_argument('--no-progress-bar', '-n', action='store_true')
    parser.add_argument('dir', nargs='+')
    parser.set_defaults(func=preview_func)
