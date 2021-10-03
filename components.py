import os
import re
import datetime as dt
import threading as thr
import shutil as sh
import configparser as cfg

config = cfg.ConfigParser()
config.read('plex.cfg')


class Contants:
    LOG_FILE = 'plex.log'

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


class LogComponent:
    '''A thread-safe class for logging info to stdout or a specified file'''

    def __init__(self, stdout=True, path=None, divider='='):
        self._divider = divider

        if not stdout and path is None:
            print('[-]: a path is required when stdout is False')
            stdout = True

        if stdout and path is None:
            # only write to stdout
            def _print_wrapper(*values, **kwargs):
                print(*values, **kwargs)

        elif stdout and path is not None:
            # write to log and stdout
            def _print_wrapper(*values, **kwargs):
                with open(path, 'a') as log_file:
                    print(*values, **kwargs, file=log_file)
                print(*values, **kwargs)

        else:
            # only write to log
            def _print_wrapper(*values, **kwargs):
                with open(path, 'a') as log_file:
                    print(*values, **kwargs, file=log_file)

        self._write_func = _print_wrapper

        self._is_enabled = True
        self._print_lock = thr.Lock()

    def message(self, text):
        lines = text.split('\n')

        if self._is_enabled:
            with self._print_lock:
                for text in lines:
                    self._write_func(f'[{dt.datetime.now()}]: {text}')

    def disable(self):
        self._is_enabled = False

    def header(self, header_text: str):
        header_text = header_text.upper().replace('_', ' ')

        self.message(self._divider * 80)
        self.message(f'{header_text.upper():*^80}')
        self.message(self._divider * 80)

    def divider(self):
        self.message(self._divider * 80)


class Output:
    log = LogComponent(path=Contants.LOG_FILE)

    log.header('loading file mover components')


class FileMover:
    src_path = None
    tgt_path = None

    @staticmethod
    def list_files_on_source():
        pass

    @staticmethod
    def list_files_on_target():
        pass

    @staticmethod
    def move_files():
        pass


class MovieMover(FileMover):
    src_path = config['movies']['src_path'].replace('\\', '/')
    tgt_path = config['movies']['tgt_path'].replace('\\', '/')

    @staticmethod
    def list_files_on_source():
        movies_folder = os.walk(MovieMover.src_path)

        all_files = list()

        for root, _, files in movies_folder:
            for file in files:
                all_files.append((root, file))

        return all_files

    @staticmethod
    def list_files_on_target():
        movies_folder = os.walk(MovieMover.tgt_path)

        all_files = list()

        for root, _, files in movies_folder:
            for file in files:
                all_files.append((root, file))

        return all_files

    @staticmethod
    def move_files(name_changes: list) -> list:
        name_changes = sorted(name_changes, key=lambda n: n[2])

        manifest = list()

        Output.log.header('processing duplicates')

        for path, old_name, new_name in name_changes:
            old_location = path + '/' + old_name
            new_location = MovieMover.tgt_path + '/' + new_name

            if os.path.isfile(new_location):
                Output.log.message(f'[SKIP]\t{new_name}')
                continue

            manifest.append((path, old_location, new_location))

        Output.log.header('deployment manifest')

        for idx, (path, _, new_name) in enumerate(manifest):
            Output.log.message(f'[{str(idx).zfill(2)}]\t{new_name}')

        Output.log.divider()

        for path, old_name, new_name in manifest:
            Output.log.message(f'OLD:\t{old_name}')
            Output.log.message(f'NEW:\t{new_name}')
            sh.copyfile(old_name, new_name)

        Output.log.header('deployment complete')


class TvShowMover(FileMover):

    src_path = config['tv']['src_path'].replace('\\', '/')
    tgt_path = config['tv']['tgt_path'].replace('\\', '/')

    move = sh.copyfile

    overwrite = False

    @staticmethod
    def list_files_on_source():
        return os.listdir(TvShowMover.src_path)

    @staticmethod
    def list_files_on_target():
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
        TvShowMover.move = \
            (os.rename if TvShowMover.tgt_path == os.path.normpath(path)
             else sh.copyfile)

    @staticmethod
    def move_files(changes):
        errors = []

        for old_path, new_path in changes:

            if not TvShowMover.overwrite and os.path.isfile(new_path):
                Output.log.message(f'[SKIP]\t{new_path}')
                continue

            try:
                Output.log.message(f'OLD:\t{old_path.split("/")[-1]}')
                Output.log.message(f'NEW:\t{new_path}')

                TvShowMover.move(old_path, new_path)
            except Exception as e:
                Output.log.message(e)
                errors.append((old_path, new_path))

        if len(errors) > 0:
            Output.log.message('reattempting errors')
            for old_path, new_path in errors:
                try:
                    Output.log.message(f'OLD:\t{old_path.split("/")[-1]}')
                    Output.log.message(f'NEW:\t{new_path}')
                    TvShowMover.move(old_path, new_path)

                except Exception as e:
                    Output.log.message(e)
                    continue

    @staticmethod
    def move_specials(odd_names):
        Output.log.message('moving oddly-named files to s00')
        for old_path, new_path in odd_names:
            try:
                Output.log.message(f'OLD:\t{old_path.split("/")[-1]}')
                Output.log.message(f'NEW:\t{new_path}')
                sh.copyfile(old_path, new_path)
            except Exception as e:
                Output.log.message(e)
                continue
