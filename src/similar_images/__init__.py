import argparse

from . import constants
from . import preview
from . import post_preview

def parse_args():
    parser = argparse.ArgumentParser(
        prog='similar-images',
        description='Finds and removes similar images')
    parser.add_argument('--app-cache-dir', default=constants.default_cache_dir())
    subparsers = parser.add_subparsers()
    preview.add_subparser(subparsers)
    post_preview.add_subparser(subparsers)
    args = parser.parse_args()
    return args


def cli_main():
    args = parse_args()
    # args.func is setup by the individual *.add_subparser() calls above
    args.func(args)
