import platformdirs
from pathlib import Path

app_name = 'similar-images'
db_cache_version = 1
digest = 'sha1'

progress_bar_min_missing_imghashes = 200


def default_cache_dir():
    return platformdirs.user_cache_dir(appname=app_name)
