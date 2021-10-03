import os
import re
import shutil as sh
import configparser as cfg

config = cfg.ConfigParser()
config.read('plex.cfg')


class Contants:
    PREFERRED_VIDEO_EXTENSIONS = {'mkv', 'mp4'}

    OTHER_VIDEO_EXTENSIONS = {'flv', 'f4p', 'ogv', 'asf', 'amv', 'mpg',
                              'f4b', 'yuv', 'nsv', 'svi', 'mov', 'f4v',
                              'qt', '3gp', 'mxf', 'mp2', 'gif', 'roq',
                              'drc', 'gifv', 'mpe', 'rm', 'wmv', 'webm',
                              'mpeg', 'ogg', 'm2v', 'mng', 'm2ts', 'mts',
                              'avi', 'rmvb', 'vob', 'm4v'}

    SUBTITLE_EXTENSIONS = {'srt', 'idx', 'sub'}

    class Tv:
        EPISODE_REGEX = (r'(?P<episode>'  # start episode group

                         # eg s01 or S01 or 1
                         r'(?P<season>[sS]?(?P<season_num>\d+))?'

                         # episode number: e01 or E01 or x01
                         # optionally, preceding "_", "-", or " "
                         r'[\-_ ]?[xeE](?P<episode_num>\d+)'

                         # detects multi-episode file
                         # (-e02, -E02, ,-x02, -02)
                         r'(?P<episode_num_ext>-?[xeE]?\d+)?'

                         # close episode group
                         r')'

                         # detects multi-part episode
                         r'(?P<part_num>-(pt|part)\d)?')

    class Movies:
        YEAR_REGEX_PATTERN = r'^.+__(?P<year>(19|20)\d{2}).+$'
        TITLE_REGEX_PATTERN = r'^(?P<title>[a-zA-Z0-9 \'\-!_&]+).+$'
        VALID_NAME_PATTERN = r'[^a-z0-9\._]'

        COMMON_TOKENS = {'web', 'bluray', 'dvdrip', '2160p', '1080p', '720p',
                         '4k', 'hd', 'x264', 'x265', '5.1'}


class MovieMover:
    src_path = config['movies']['src_path']
    tgt_path = config['movies']['tgt_path']

    @staticmethod
    def list_files_on_source():
        movies_folder = os.walk(MovieMover.src_path)

        all_files = list()

        for root, _, files in movies_folder:
            for file in files:
                all_files.append((root, file))

        return all_files

    @staticmethod
    def move_files(name_changes: list) -> list:
        name_changes = sorted(name_changes, key=lambda n: n[2])

        manifest = list()

        print('=' * 80)
        print(f'{"Processing Duplicates":*^80}')
        print('=' * 80)

        for path, old_name, new_name in name_changes:
            old_location = path + '\\' + old_name
            new_location = MovieMover.tgt_path + '\\' + new_name

            if os.path.isfile(new_location):
                print(f'skipping {new_name}')
                continue

            manifest.append((path, old_location, new_location))

        print('=' * 80)
        print(f'{"Deployment Manifest":*^80}')
        print('=' * 80)

        for idx, (path, _, new_name) in enumerate(manifest):
            print(f'[{str(idx).zfill(2)}]: {new_name}')

        print('=' * 80)

        while True:
            confirm_deploy = input('Begin deployment? (y/n): ').lower().strip()

            if confirm_deploy not in ('y', 'n'):
                print(f'{confirm_deploy} is an invalid entry')
                continue
            break

        if confirm_deploy == 'n':
            return

        for path, old_name, new_name in manifest:
            print(f'\nOld: {old_name}\nNew: {new_name}')
            sh.copyfile(old_name, new_name)

        print('=' * 80)
        print(f'{"Deployment Complete":*^80}')
        print('=' * 80)


class TvShowMover:

    src_path = config['tv']['src_path']
    tgt_path = config['tv']['tgt_path']

    operation = sh.copyfile

    overwrite = False

    @staticmethod
    def list_shows_on_source():
        return os.listdir(TvShowMover.src_path)

    @staticmethod
    def list_shows_on_target():
        return os.listdir(TvShowMover.tgt_path)

    @staticmethod
    def get_tv_show_files(tv_show_name: str):
        tv_show_folder = os.walk(TvShowMover.src_path + '/' + tv_show_name)

        tv_show = []
        for root, _, files in tv_show_folder:
            try:
                season_folder = str(re.split(r'[\\\/]+', root)[::-1][0])
            except IndexError:
                continue

            season_num_match = re.search(r'[sS](\d+)', season_folder)
            if not season_num_match:
                season_num_match = \
                    re.search(r'[sS]eason[ ._-](\d+)', season_folder)

            if season_num_match:
                season_num = season_num_match.group(1)
                season_num = season_num.zfill(2)
                season = 's' + season_num
            else:
                season = 's00'

            tv_show = tv_show + [(root, season, f) for f in files]

        return tv_show

    @staticmethod
    def allocate_space_for_show(tv_show_name: str):
        if not os.path.exists(TvShowMover.tgt_path + '/' + tv_show_name):
            os.makedirs(TvShowMover.tgt_path + '/' + tv_show_name)

    @staticmethod
    def allocate_space_for_season(tv_show_name: str, season: str):
        season_path = f'{TvShowMover.tgt_path}/{tv_show_name}/{season}'
        if not os.path.exists(season_path):
            os.makedirs(season_path)

    @staticmethod
    def create_specials_folder(tv_show_name: str):
        season_zero_path = f'{TvShowMover.tgt_path}/{tv_show_name}/s00'
        if not os.path.exists(season_zero_path):
            os.makedirs(season_zero_path)

    @staticmethod
    def paths_are_equal(old_path: str, new_path: str) -> bool:
        return os.path.normpath(old_path) == os.path.normpath(new_path)

    @staticmethod
    def set_overwrite(overwrite):
        TvShowMover.overwrite = overwrite

    @staticmethod
    def set_file_operation(path):
        TvShowMover.operation = \
            (os.rename if TvShowMover.tgt_path == os.path.normpath(path)
             else sh.copyfile)

    @staticmethod
    def move_changes(changes):
        errors = []

        for old_path, new_path in changes:

            if not TvShowMover.overwrite and os.path.isfile(new_path):
                print(f'{old_path} -/-> {new_path} (already exists)')
                continue

            try:
                print(f'{old_path} ---> {new_path}')

                TvShowMover.operation(old_path, new_path)
            except Exception as e:
                print(e)
                errors.append((old_path, new_path))

        if len(errors) > 0:
            print('reattempting errors')
            for old_path, new_path in errors:
                try:
                    print(f'{old_path} --> {new_path}')
                    TvShowMover.operation(old_path, new_path)

                except Exception as e:
                    print(e)
                    continue

    @staticmethod
    def move_odd_names(odd_names):
        print('moving oddly-named files to s00')
        for old_path, new_path in odd_names:
            try:
                print(f'{old_path} --> {new_path}')
                sh.copyfile(old_path, new_path)
            except Exception as e:
                print(e)
                continue
