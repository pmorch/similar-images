from rich import print as rprint

from . import preview
from . import image_processing

keep_by_help = '''
By default we keep the best image: with the biggest size and highest resolution.
If these are not the same, i.e. one image is the largest in bytes and the other
has highest number of bytes, a warning is shown and nothing is done.
'''

name_by_help = '''
Likely an obscure option. By default, we keep the biggest image as described
under --keep-by. --name-by=first will move the biggest image to replace the
first image, keeping the biggest file with the filename of the first image. This
is handy if the first directory has better order but lower quality photos.
'''

dups_help = '''
Which dup sets, as either the string "obvious" meaing all obvious sets, or
comma-separated numbers, to apply the action to. If not given, the action will
apply to all dup sets. E.g. "obvious" or "5,7,11".
'''


def add_show_dedup_args(parser):
    parser.add_argument(
        '--keep-by',
        choices=['best', 'most-pixels', 'most-bytes', 'first'],
        default='best',
        help=keep_by_help)
    parser.add_argument(
        '--name-by',
        choices=['keep-by', 'first'],
        default='keep-by',
        help=name_by_help)
    parser.add_argument('--dups', help=dups_help)
    parser.add_argument('--no-progress-bar', '-n', action='store_true')
    parser.add_argument('dir', nargs='+')


def get_categorized_dups(args):
    dups = image_processing.find_dups(
        args.app_cache_dir, args.dir, not (args.no_progress_bar))

    obvious = []
    unclear = []

    if args.dups and args.dups != "obvious":
        dup_indexes = set([int(x)-1 for x in args.dups.split(',')])
    else:
        dup_indexes = None

    for i, dup in enumerate(dups):
        if dup_indexes is not None and i not in dup_indexes:
            continue
        if dup.is_obvious():
            obvious.append([i, dup])
        elif not args.dups or args.dups != "obvious":
            unclear.append([i, dup])
    return obvious, unclear

def show_func(args):
    obvious, unclear = get_categorized_dups(args)
    def handle_dup(dup):
        for action in dup.actions(args.keep_by, args.name_by):
            print("    " + str(action))
        for j, tuple in enumerate(dup.paths_with_evaluations()):
            path, evaluation = tuple
            rprint("    [blue]# %d: %-11s: %s" % (j, evaluation, path))

    for (i, dup) in obvious:
        rprint("[green]obvious-%d" % (i+1))
        handle_dup(dup)

    for (i, dup) in unclear:
        rprint("[magenta]unclear-%d" % (i+1))
        if args.keep_by == "best" and not (dup.is_obvious()):
            rprint('    [red]*Warning*: unclear which is best')
            for j, tuple in enumerate(dup.paths_with_evaluations()):
                p, e = tuple
                print("    %d: %-11s: %s" % (j, e, p))
            continue
        handle_dup(dup)

def dedup_func(args):
    obvious, unclear = get_categorized_dups(args)
    def handle_dup(dup):
        for action in dup.actions(args.keep_by, args.name_by):
            action.execute()

    for (i, dup) in obvious:
        handle_dup(dup)

    for (i, dup) in unclear:
        if args.keep_by == "best" and not (dup.is_obvious()):
            rprint('    [red]unclear-%d : *Warning*: unclear which is best' % (i+1))
            continue
        handle_dup(dup)


def add_subparser(subparsers):
    show_parser = subparsers.add_parser(
        'show', help='Show what dedup actions can be taken')
    add_show_dedup_args(show_parser)
    show_parser.set_defaults(func=show_func)

    dedup_parser = subparsers.add_parser(
        'dedup', help='Actually dedup and perform actions listed by "show"')
    add_show_dedup_args(dedup_parser)
    dedup_parser.set_defaults(func=dedup_func)
