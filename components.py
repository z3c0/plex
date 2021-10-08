import os
import re
import datetime as dt
import queue as q
import threading as thr
import shutil as sh
import configparser as cfg

config = cfg.ConfigParser()
config.read('plex.cfg')


class Contants:
    LOG_FILE = 'plex.log'

    THREAD_COUNT = 8

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

    def __init__(self, stdout=True, path=None, divider='=', pad='-', width=80):

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
        self._divider = divider
        self._pad = pad
        self._width = width

    def message(self, text):
        lines = text.split('\n')

        if self._is_enabled:
            with self._print_lock:
                for text in lines:
                    text = (text[:self._width - 3] + '...'
                            if len(text) > self._width
                            else text)
                    self._write_func(f'[{dt.datetime.now()}]: {text}')

    def submessage(self, text, header=''):
        if header != '':
            header = f'[{header}]'

        self.message(f'|- {header} {text}')

    def disable(self):
        self._is_enabled = False

    def header(self, header_text: str):
        header_text = header_text.upper().replace('_', ' ')

        header_text = header_text.center(self._width, self._pad)

        self.message(self._divider * self._width)
        self.message(header_text)
        self.message(self._divider * self._width)

    def divider(self):
        self.message(self._divider * self._width)


class Output:
    log = LogComponent(path=Contants.LOG_FILE)


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

    move = sh.copyfile

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
    def run_threads(queue, changes, func):
        for _ in range(Contants.THREAD_COUNT):
            thread = thr.Thread(target=func, daemon=True)
            thread.start()

        try:
            for idx, (old_path, new_path) in enumerate(changes):
                queue.put(((idx + 1) * -1, old_path, new_path))

            queue.join()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            Output.log.message(e)

            MovieMover.remove_files((tgt for _, tgt in changes))

        finally:
            for _ in range(Contants.THREAD_COUNT):
                queue.put((0, None, None))

            while not queue.empty():
                _ = queue.get_nowait()

    @staticmethod
    def process_manifest(changes: list) -> list:
        manifest = list()

        Output.log.header('processing duplicates')

        for old_path, new_name in changes:
            new_path = MovieMover.tgt_path + '/' + new_name

            if os.path.isfile(new_path):
                Output.log.message(f'[SKIP] {new_name}')
                continue

            manifest.append((old_path, new_path))

        Output.log.header('deployment manifest')

        for idx, (_, new_path) in enumerate(manifest):
            Output.log.message(f'[{str(idx).zfill(2)}] {new_path}')

        Output.log.divider()

        return manifest

    @staticmethod
    def move_files(changes: list):
        '''
            changes is a list of 2-tuples
            changes[n][0] contains the path of the file to be moved
            changes[n][1] contains the desired name of the file
        '''
        changes = sorted(changes, key=lambda n: n[1])

        manifest = MovieMover.process_manifest(changes)

        queue = q.PriorityQueue(Contants.THREAD_COUNT)
        errors = []

        def move_files_thread():
            while True:
                priority_id, old_path, new_path = queue.get()

                if priority_id == 0:
                    queue.task_done()
                    break

                try:
                    file_name = new_path.split("/")[-1]
                    old_name = old_path.split("/")[-1]

                    Output.log.message(f'[MOVE] {file_name} ({old_name})')
                    MovieMover.move(old_path, new_path)
                    Output.log.message(f'[DONE] {file_name}')

                except Exception as e:
                    Output.log.message(e.text)
                    errors.append((old_path, new_path))
                    raise
                finally:
                    queue.task_done()

        TvShowMover.run_threads(queue, manifest, move_files_thread)

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
    def remove_files(paths):
        for path in paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                continue

    @staticmethod
    def run_threads(queue, changes, func):
        for _ in range(Contants.THREAD_COUNT):
            thread = thr.Thread(target=func, daemon=True)
            thread.start()

        try:
            for idx, (old_path, new_path) in enumerate(changes):
                queue.put(((idx + 1) * -1, old_path, new_path))

            queue.join()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            Output.log.message(e)

            TvShowMover.remove_files((tgt for _, tgt in changes))

        finally:
            for _ in range(Contants.THREAD_COUNT):
                queue.put((0, None, None))

            while not queue.empty():
                _ = queue.get_nowait()

    @staticmethod
    def move_files(changes):
        errors = []

        queue = q.PriorityQueue(len(changes))

        def move_files_thread():
            while True:
                priority_id, old_path, new_path = queue.get()

                if priority_id == 0:
                    queue.task_done()
                    break

                if not TvShowMover.overwrite and os.path.isfile(new_path):
                    Output.log.message(f'[SKIP] {new_path.split("/")[-1]}')
                    queue.task_done()
                    continue

                try:
                    file_name = new_path.split("/")[-1]
                    old_name = old_path.split("/")[-1]

                    Output.log.message(f'[MOVE] {file_name} ({old_name})')
                    TvShowMover.move(old_path, new_path)
                    Output.log.message(f'[DONE] {file_name}')

                except Exception as e:
                    Output.log.message(e)
                    errors.append((old_path, new_path))

                queue.task_done()

        TvShowMover.run_threads(queue, changes, move_files_thread)

        # clean-up half-processed files for re-attempting
        TvShowMover.remove_files((tgt for _, tgt in errors))

    @staticmethod
    def move_specials(odd_names):
        Output.log.message('moving oddly-named files to s00')
        for old_path, new_path in odd_names:
            try:
                file_name = new_path.split("/")[-1]
                old_name = old_path.split("/")[-1]

                Output.log.message(f'[MOVE] {file_name} ({old_name})')
                TvShowMover.move(old_path, new_path)
                Output.log.message(f'[DONE] {file_name}')
            except Exception as e:
                Output.log.message(e)
                continue
