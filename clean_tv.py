#!python3.8.5

import re

from components import Contants, Output, TvShowMover


def main():
    move_tv_files()


def move_tv_files():
    tv_shows = TvShowMover.list_files_on_source()

    for tv_show in tv_shows:
        clean_tv_show(tv_show)


def clean_existing_tv_files():
    # retroactively cleans existing files on target file system
    tv_shows = TvShowMover.list_files_on_target()

    for tv_show in tv_shows:
        clean_tv_show(tv_show, TvShowMover.tgt_path)


def get_season_num_from_episode(episode_file_name: str) -> str:
    season_num = re.search(r'([sS]\d+)', episode_file_name)
    season_num = season_num.group(1) if season_num else None
    season_num = season_num.lower() if season_num else None
    return season_num


def name_special_file(episode_file_name: str) -> str:
    all_symbols = r'[ \-\[\]+=,./;:\'`~!@#$%^&*]'
    new_name = re.sub(all_symbols, '_', episode_file_name)
    new_name = re.sub(r'_+', '_', new_name).lower()
    return new_name


def clean_num_ext(episode_num_ext: str) -> str:
    episode_num_ext.lower()
    if episode_num_ext[1] != 'e':
        episode_num_ext = '-e' + episode_num_ext[1:]

    return episode_num_ext


def parse_episode_match(episode_match: re.Match, season_folder: str) -> str:
    groups = episode_match.groupdict()
    episode_num = groups['episode'].lower().replace(' ', '')
    season_num = groups['season_num']

    season = 's' + season_num.zfill(2) if season_num else season_folder

    episode_num = groups['episode_num'].lower()

    episode_num_ext = groups['episode_num_ext']
    episode_num_ext = (clean_num_ext(episode_num_ext)
                       if episode_num_ext
                       else '')

    part_num = (groups['part_num'].lower().replace('part', 'pt')
                if groups['part_num']
                else '')

    episode_num = episode_num.zfill(2)

    episode = season + 'e' + episode_num + episode_num_ext + part_num

    return episode


def clean_tv_show(tv_show_name: str, path=TvShowMover.src_path):
    TvShowMover.set_file_operation(path)
    TvShowMover.allocate_space_for_show(tv_show_name)

    tv_show = TvShowMover.get_tv_show_files(tv_show_name)

    if len(tv_show) == 0:
        return

    Output.log.header(tv_show_name)

    changes = []
    odd_names = []

    for root, folder_season, episode_file in tv_show:
        # skip hidden files
        if episode_file[0] == '.' or not re.match(r's\d+', folder_season):
            continue

        season_num = get_season_num_from_episode(episode_file)
        season = (season_num if season_num and season_num != folder_season
                  else folder_season)

        episode_match = \
            re.search(Contants.Tv.EPISODE_REGEX, episode_file)
        episode_ext_match = re.search(r'^.+\.([a-z0-9]{2,4})$', episode_file)

        if not episode_ext_match:
            continue

        episode_ext = episode_ext_match.group(1).lower()

        valid_extensions = (Contants.PREFERRED_VIDEO_EXTENSIONS
                            .union(Contants.OTHER_VIDEO_EXTENSIONS)
                            .union(Contants.SUBTITLE_EXTENSIONS))

        if episode_ext not in valid_extensions:
            continue

        if not episode_match:
            new_name = name_special_file(episode_file)

            old_path = root + '/' + episode_file
            new_path = f'{TvShowMover.tgt_path}/{tv_show_name}/s00/{new_name}'

            odd_names.append((old_path, new_path))
            continue

        episode = parse_episode_match(episode_match, folder_season)

        new_path = (f'{TvShowMover.tgt_path}/{tv_show_name}/{season}/'
                    f'{episode}.{episode_ext}')
        old_path = root + '/' + episode_file

        TvShowMover.allocate_space_for_season(tv_show_name, season)

        if not TvShowMover.paths_are_equal(old_path, new_path):
            changes.append((old_path, new_path))

    if len(changes) > 0:
        TvShowMover.move_files(changes)

    if len(odd_names) > 0:
        TvShowMover.create_specials_folder(tv_show_name)
        TvShowMover.move_specials(odd_names)


if __name__ == '__main__':
    main()
