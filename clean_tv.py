
from mediamanager import TvMover


def clean_existing_tv_files():
    """retroactively cleans existing files on the target file system"""
    # !!! BE VERY CAREFUL RUNNING THIS FUNCTION !!!
    # As a precaution, back up the files on your target system before running,
    # as this function edits files directly on the target system,
    # without staging the changes first. A failure could result in data-loss.

    tv_shows = TvMover.list_tv_shows_on_target()
    for tv_show in tv_shows:
        TvMover.clean_tv_show(tv_show, TvMover.tgt_path)


def move_tv_files():
    """move TV shows from the source system to the target system"""
    tv_shows = TvMover.list_tv_shows_on_source()
    TvMover.move_tv_shows(tv_shows)


if __name__ == '__main__':
    move_tv_files()
