"""module for preparing movie files for Plex"""

from components import MovieMover


def main():
    """The main method"""
    process_movies()


def process_movies():
    """Renames movies to a cleaner format at the given path"""
    all_files = MovieMover.list_files_on_source()

    videos, subtitles = MovieMover.search(all_files)
    name_changes = MovieMover.process_new_titles(videos, subtitles)
    MovieMover.move_files(name_changes)


if __name__ == '__main__':
    main()
