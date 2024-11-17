"""
# Algorithm

## Multiple source directories

The user supplies an array of directories to find images in, and sequence could
matter. Imagine:

    /some/dir
        subdirA/
            img1.jpg, img2.jpg, img3.jpg
        imgA.jpg, imgB.jpg, imgC.jpg

It could be that the images in subdirA are in the proper order, but have
duplicates within the rest of /some/dir. Then the user can give:

    [ '/some/dir/subdirA', '/some/dir' ]

to say that the images in subdirA should be considered "first". We make sure
imgA-C.jpg is not be included twice even though it is in both input paths.

This results in a full list of the images we want to consider.

## Getting an imagehash

The imagehash module is great in that it comes up with a hash for images, so if
two instances of the "same" image are scaled differently (higher/lower res,
more/less bytes), they end up with the same imagehash.

The problem is that image hashing is slow. And the user might want create
multiple previews, rearranging images in between, so using the file name as a
key is not ideal. Luckily digests like SHA1 of files are fast in comparison,
and are stable accross renames.

So for the full list of files, we first get SHA1 sums of their contents.

This is used as a key for a db cache to store the imagehashes per SHA1 sum so we
can know which SHA1 sums we've never seen before and store them for next
iterations.

## Full algorithm

* Get full list of files
* Generate SHA1 sums for all of them
* Determine which SHA1 sums we don't yet have imagehashes for in the cache
* Generate imagehashes for these files
* Update the cache
* Group files by imagehashes, and each group is a group of duplicate files
"""

import imagehash
import hashlib
import shlex
import sqlite3
from dataclasses import dataclass
from PIL import Image
from pathlib import Path
from tqdm import tqdm

from . import constants


def _indices_with_max_value(list):
    max_value = max(list)
    indices = set()
    for i, v in enumerate(list):
        if v == max_value:
            indices.add(i)
    return indices


@dataclass
class Dup:
    paths: list[str]

    def _find_best_by_bytes(self):
        # only do this once
        if not hasattr(self, "_best_by_bytes"):
            sizes = [Path(p).stat().st_size for p in self.paths]
            self._best_by_bytes = _indices_with_max_value(sizes)
        return self._best_by_bytes

    def _find_best_by_pixels(self):
        def pixel_size(path):
            im = Image.open(path)
            w, h = im.size
            return w * h
        # only do this once
        if not hasattr(self, "_best_by_pixels"):
            sizes = [pixel_size(p) for p in self.paths]
            # self._best_by_pixels = max(range(len(sizes)), key=sizes.__getitem__)
            self._best_by_pixels = _indices_with_max_value(sizes)
        return self._best_by_pixels

    def _firsts(self):
        bb_bytes = self._find_best_by_bytes()
        bb_pixels = self._find_best_by_pixels()
        best = bb_bytes.intersection(bb_pixels)

        first_bb_bytes = sorted(list(bb_bytes))[
            0] if len(bb_bytes) > 0 else None
        first_bb_pixels = sorted(list(bb_pixels))[
            0] if len(bb_pixels) > 0 else None
        first_best = sorted(list(best))[0] if len(best) > 0 else None

        return first_best, first_bb_pixels, first_bb_bytes

    def is_obvious(self):
        first_best, _, _ = self._firsts()
        return first_best is not None

    def paths_with_evaluations(self):
        first_best, first_bb_pixels, first_bb_bytes = self._firsts()

        for i, path in enumerate(self.paths):
            if i == first_best:
                yield path, "best"
            elif first_best is None and i == first_bb_bytes:
                yield path, "most-bytes"
            elif first_best is None and i == first_bb_pixels:
                yield path, "most-pixels"
            else:
                yield path, "delete"

    def actions(self, keep_by, name_by):
        first_best, first_bb_pixels, first_bb_bytes = self._firsts()
        match keep_by:
            case 'best':
                if first_best is None:
                    raise RuntimeError("Want best but there is no best")
                keep_index = first_best
            case 'most-pixels':
                keep_index = first_bb_pixels
            case 'most-bytes':
                keep_index = first_bb_bytes
            case 'first':
                keep_index = 0
            case _:
                raise RuntimeError("Unexpected keep_by: " + keep_by)
        match name_by:
            case "keep-by":
                for i, p in enumerate(self.paths):
                    if i != keep_index:
                        yield DupRmAction(dup=self, dst=i)
            case "first":
                if keep_index != 0:
                    yield DupMvToFirstAction(self, keep_index)
                for i, p in enumerate(self.paths):
                    if i != 0 and i != keep_index:
                        yield DupRmAction(dup=self, dst=i)
            case _:
                raise RuntimeError("Unexpected name_by: " + name_by)


@dataclass
class DupRmAction:
    dup: Dup
    dst: int

    def __str__(self):
        return "rm %s # %d" % (shlex.quote(self.dup.paths[self.dst]), self.dst)

    def execute(self):
        Path(self.dup.paths[self.dst]).unlink()


@dataclass
class DupMvToFirstAction:
    dup: Dup
    src: int

    def __str__(self):
        return "mv %s %s" % (
            shlex.quote(self.dup.paths[self.src]),
            shlex.quote(self.dup.paths[0])
        )

    def execute(self):
        Path(self.dup.paths[self.src]).rename(self.dup.paths[0])


def _dups_from_raw(raw_dups):
    dups = []
    for rd in raw_dups:
        dup = Dup(paths=rd)
        dups.append(dup)
    return dups


def is_image(filename):
    f = filename.lower()
    return f.endswith('.png') or f.endswith('.jpg') or \
        f.endswith('.jpeg') or f.endswith('.bmp') or \
        f.endswith('.gif') or '.jpg' in f or f.endswith('.svg')


def find_image_paths(src_paths: list[str]) -> list[str]:
    paths = []
    seen_paths = set()
    for src_path in src_paths:
        for file in sorted(Path(src_path).rglob('*')):
            if str(file) in seen_paths:
                continue
            seen_paths.add(str(file))
            if is_image(file.name):
                paths.append(str(file))
    return paths


def _get_db_con(app_cache_dir):
    app_cache_dir = Path(app_cache_dir)
    if not app_cache_dir.exists():
        app_cache_dir.mkdir()

    db_file = app_cache_dir / (
        'imagehashcache-v%d.db' % constants.db_cache_version)

    pre_exists = db_file.exists()
    con = sqlite3.connect(db_file)
    if not pre_exists:
        cur = con.cursor()
        cur.execute('create table imagehashes(digest, imagehash)')
        con.commit()
    return con


def _find_digest_imagehash(con, digest):
    cur = con.cursor()
    res = cur.execute(
        'select imagehash from imagehashes where digest=?', (digest,))
    one = res.fetchone()
    if one is None:
        return None
    hash, = one
    return hash


def _insert_digest_imagehashes(con, insert_params):
    cur = con.cursor()
    res = cur.executemany(
        'insert into imagehashes (digest, imagehash) VALUES (?,?)', insert_params)
    con.commit()


# I don't think this is being used..
def time_func(name, func, *args):
    """prints the wall time it takes to execute func(args)"""
    import time
    start_time = time.time()
    return_value = func(*args)
    end_time = time.time()
    print(f"{name} took {end_time - start_time} seconds")
    return return_value


def get_digests(paths):
    """get_digests returns digests for all file paths"""
    digests = []
    for path in paths:
        with open(path, 'rb', buffering=0) as f:
            digest = hashlib.file_digest(f, constants.digest).hexdigest()
        digests.append(digest)
    return digests


def get_imagehashes(app_cache_dir, paths, show_progress_bar):
    digests = get_digests(paths)
    con = _get_db_con(app_cache_dir)

    # These have digests as keys
    imghashes = {}
    missing_imghashes = {}

    for i, digest in enumerate(digests):
        if digest in imghashes or digest in missing_imghashes:
            continue
        imghash = _find_digest_imagehash(con, digest)
        if imghash is None:
            missing_imghashes[digest] = paths[i]
        else:
            imghashes[digest] = imghash

    hashfunc = imagehash.average_hash

    if show_progress_bar and len(missing_imghashes) > constants.progress_bar_min_missing_imghashes:
        iterate_over = tqdm(missing_imghashes)
    else:
        iterate_over = missing_imghashes

    insert_params = []
    for digest in iterate_over:
        spath = str(missing_imghashes[digest])
        try:
            imghash = str(hashfunc(Image.open(spath)))
        except Exception as e:
            raise RuntimeError('Problem:', e, 'with', spath)
        insert_params.append([digest, imghash])
        imghashes[digest] = imghash
    if len(insert_params) > 0:
        _insert_digest_imagehashes(con, insert_params)

    path_imghashes = {}
    for i, path in enumerate(paths):
        digest = digests[i]
        path_imghashes[path] = imghashes[digest]
    return path_imghashes


def group_duplicate_images_by_hash(paths, hashes):
    images_by_hash = {}
    for image in paths:
        if not image in hashes:
            raise RuntimeError("Expected a hash for %s" % image)
        hash = hashes[image]
        images_by_hash[hash] = images_by_hash.get(hash, []) + [image]
    dups = []
    for hash in images_by_hash:
        if len(images_by_hash[hash]) > 1:
            dups.append(images_by_hash[hash])
    return dups


def find_dups(app_cache_dir: str, src_paths: list[str], show_progress_bar: bool):
    paths = find_image_paths(src_paths)
    hashes = get_imagehashes(app_cache_dir, paths, show_progress_bar)
    dups = group_duplicate_images_by_hash(paths, hashes)
    return _dups_from_raw(dups)
