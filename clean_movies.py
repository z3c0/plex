#!python3.8
"""module for preparing movie files for Plex"""

import re
from typing import Optional


from components import Contants, MovieMover


def main():
    """The main method"""
    process_movies()


def clean_movie_name(current_name: str) -> Optional[str]:

    year = re.search(r'(19|20)[0-9]{2}', current_name)

    probably_the_name = current_name[:year.start()]

    # "꞉" and ":" are not the same
    probably_the_name = re.sub(r'[.()_:꞉, ]', '_', probably_the_name)
    probably_the_name = re.sub(r'[\']', '', probably_the_name)

    for token in Contants.Movies.COMMON_TOKENS:
        if token in probably_the_name:
            probably_the_name.replace(token, '')

    clean_name = f'{probably_the_name}_({year.group(0)})'

    while '__' in clean_name:
        clean_name = clean_name.replace('__', '_')

    if len(clean_name.strip()) > 7:
        return clean_name

    return None


def process_new_titles(video_files: list, subtitle_files: list) -> list:

    print('=' * 80)
    print(f'{"Processing New Names":*^80}')
    print('=' * 80)

    name_changes = []

    for path, file, ext in video_files:
        print(f'File: {file}')
        print(f'Type: {ext}')

        new_name = clean_movie_name(file)

        if new_name == '.' + ext:
            print('Skipped file', end='\n\n')
            continue

        print(f'{file} --> {new_name}', end='\n\n')

        sub_name = None
        for sub_path, sub_file, sub_ext in subtitle_files:
            if sub_file == file:
                sub_name = sub_file + '.' + sub_ext
                break

        name_changes.append((path, file + '.' + ext, new_name + '.' + ext))

        if sub_name:
            new_sub_name = new_name + '.eng.' + sub_ext
            name_changes.append((sub_path, sub_name, new_sub_name))

    return name_changes


def search_for_movies(all_files: list) -> list:
    video_files = list()
    subtitle_files = list()

    all_extensions = Contants.PREFERRED_VIDEO_EXTENSIONS
    all_extensions = all_extensions.union(Contants.OTHER_VIDEO_EXTENSIONS)

    extension = None
    extension_match = None

    for path, file in all_files:
        file = file.lower()
        extension_match = re.search(r'^(.+)\.([a-z0-9]{2,4})$', file)
        if not extension_match:
            continue

        name = extension_match.group(1)
        extension = extension_match.group(2)

        if extension in Contants.SUBTITLE_EXTENSIONS:
            subtitle_files.append((path, name, extension))

        if extension not in all_extensions:
            continue

        if file[0] == '.':
            continue

        if 'sample' in file:
            continue

        video_files.append((path, name, extension))

    return video_files, subtitle_files


def process_movies():
    """Renames movies to a cleaner format at the given path"""
    all_files = MovieMover.list_files_on_source()

    video_files, subtitle_files = search_for_movies(all_files)
    name_changes = process_new_titles(video_files, subtitle_files)
    MovieMover.move_files(name_changes)


if __name__ == '__main__':
    main()
