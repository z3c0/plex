
from mediamanager import TvMover


def main():
    move_tv_files()


def clean_existing_tv_files():
    # retroactively cleans existing files on target file system
    tv_shows = TvMover.list_files_on_target()

    for tv_show in tv_shows:
        TvMover.clean_tv_show(tv_show, TvMover.tgt_path)


def move_tv_files():
    tv_shows = TvMover.list_files_on_source()

    for tv_show in tv_shows:
        changes, specials = TvMover.clean_tv_show(tv_show)

        if len(changes) > 0:
            TvMover.move_files_to_stage(changes)

        if len(specials) > 0:
            TvMover.create_specials_folder(tv_show)
            TvMover.move_specials(specials)

        TvMover.move_files_to_target()
        TvMover.clear_stage(tv_show)


if __name__ == '__main__':
    main()
