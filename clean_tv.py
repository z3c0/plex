#!python3.8.5

import re

from components import Contants, TvShowMover


def main():
    move_tv_files()


def move_tv_files():
    tv_shows = TvShowMover.list_shows_on_target()

    for tv_show in tv_shows:
        clean_tv_show(tv_show)


def clean_existing_tv_files():
    # retroactively cleans existing files on target file system
    tv_shows = TvShowMover.list_shows_on_target()

    for tv_show in tv_shows:
        clean_tv_show(tv_show, TvShowMover.tgt_path)

    print('TV files cleaned')


def clean_tv_show(tv_show_name: str, path=TvShowMover.src_path):
    TvShowMover.set_file_operation(path)
    TvShowMover.allocate_space_for_show(tv_show_name)

    tv_show = TvShowMover.get_tv_show_files(tv_show_name)

    changes = []
    odd_names = []

    for root, season, episode_file in tv_show:
        # skip hidden files
        if episode_file[0] == '.':
            continue

        if not re.match(r's\d+', season):
            print(f'skipping {season}/{episode_file} (season not detected)')
            continue

        season_num = re.search(r'([sS]\d+)', episode_file)
        season_num = season_num.group(1) if season_num else None
        season_num = season_num.lower() if season_num else None
        if season_num is not None and season_num != season:
            season = season_num

        episode_name_match = \
            re.search(Contants.Tv.EPISODE_REGEX, episode_file)
        episode_ext_match = re.search(r'^.+\.([a-z0-9]{2,4})$', episode_file)

        if not episode_name_match:
            # save to be moved to s00
            all_symbols = r'[ \-\[\]+=,./;:\'`~!@#$%^&*]'
            new_name = re.sub(all_symbols, '_', episode_file)
            new_name = re.sub(r'_+', '_', new_name).lower()
            old_path = root + '/' + episode_file
            new_path = \
                f'{TvShowMover.tgt_path}/{tv_show_name}/s00/{new_name}'

            if TvShowMover.paths_are_equal(old_path, new_path):
                continue

            TvShowMover.create_specials_folder(tv_show_name)

            odd_names.append((old_path, new_path))
            continue

        groups = episode_name_match.groupdict()
        episode = groups['episode'].lower().replace(' ', '')
        season_num = groups['season_num']

        if season_num and season == 's00':
            season = 's' + season_num.zfill(2)

        episode_num = groups['episode_num'].lower()

        episode_num_ext = groups['episode_num_ext']
        if episode_num_ext:
            episode_num_ext = episode_num_ext.lower()
            if episode_num_ext[1] != 'e':
                episode_num_ext = '-e' + episode_num_ext[1:]
        else:
            episode_num_ext = ''

        if groups['part_num']:
            part_num = groups['part_num'].lower().replace('part', 'pt')
        else:
            part_num = ''

        episode_num = episode_num.zfill(2)

        episode = season + 'e' + episode_num + episode_num_ext + part_num

        if not episode_ext_match:
            print(f'Skipping {episode_file} (missing file extension)')
            continue
        else:
            episode_ext = episode_ext_match.group(1).lower()

        valid_extensions = (Contants.PREFERRED_VIDEO_EXTENSIONS
                            .union(Contants.OTHER_VIDEO_EXTENSIONS)
                            .union(Contants.SUBTITLE_EXTENSIONS))

        if episode_ext not in valid_extensions:
            print(f'Skipping {episode_file} (invalid extension)')
            continue

        new_path = (f'{TvShowMover.tgt_path}/{tv_show_name}/{season}/'
                    f'{episode}.{episode_ext}')
        old_path = root + '/' + episode_file

        TvShowMover.allocate_space_for_season(tv_show_name, season)

        if not TvShowMover.paths_are_equal(old_path, new_path):
            changes.append((old_path, new_path))

    if len(changes) > 0:
        TvShowMover.move_changes(changes)

    if len(odd_names) > 0:
        TvShowMover.move_odd_names(odd_names)

    print(f'{tv_show_name} processed')


if __name__ == '__main__':
    main()
