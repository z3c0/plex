
import re
import threading as thr
import datetime as dt

from typing import Optional


class Constants:
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
                         r'-?[xeE]?(?P<episode_num_ext>\d+)?'

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


class Log:
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
    log = Log(path=Constants.LOG_FILE)


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


class NameCleaner:

    @staticmethod
    def movie_name(current_name: str) -> Optional[str]:
        year = list(re.finditer(r'(19|20)[0-9]{2}', current_name))[-1]

        probably_the_name = current_name[:year.start()]

        # replace spaces common symbols with underscores
        # "꞉" and ":" are not the same
        probably_the_name = re.sub(r'[.()_:꞉, ]', '_', probably_the_name)

        # remove apostrophes and brackets
        probably_the_name = re.sub(r'[\[\]\']', '', probably_the_name)

        for token in Constants.Movies.COMMON_TOKENS:
            if token in probably_the_name:
                probably_the_name.replace(token, '')

        clean_name = f'{probably_the_name}_({year.group(0)})'

        while '__' in clean_name:
            clean_name = clean_name.replace('__', '_')

        if len(clean_name.strip()) > 7:
            return clean_name

        return None

    @staticmethod
    def tv_show_name(current_name: str) -> Optional[str]:
        season = re.search(r'([sS]\d+)', current_name)

        probably_the_name = (current_name[:season.start()]
                             if season else current_name)

        # replace spaces common symbols with underscores
        # "꞉" and ":" are not the same
        probably_the_name = re.sub(r'[.()_:꞉, ]', '_', probably_the_name)

        # remove apostrophes and brackets
        probably_the_name = re.sub(r'[\[\]\']', '', probably_the_name)

        for token in Constants.Movies.COMMON_TOKENS:
            if token in probably_the_name:
                probably_the_name.replace(token, '')

        while '__' in probably_the_name:
            probably_the_name = probably_the_name.replace('__', '_')

        if len(probably_the_name.strip()) > 7:
            return probably_the_name

        return probably_the_name

    @staticmethod
    def get_season_num_from_episode(episode_file_name: str) -> str:
        season_num = re.search(r'([sS]\d+)', episode_file_name)
        season_num = season_num.group(1) if season_num else None
        season_num = season_num.lower() if season_num else None
        return season_num

    @staticmethod
    def name_special_file(episode_file_name: str) -> str:
        all_symbols = r'[ \-\[\]+=,./;:\'`~!@#$%^&*]'
        new_name = re.sub(all_symbols, '_', episode_file_name)
        new_name = re.sub(r'_+', '_', new_name).lower()
        return new_name

    @staticmethod
    def clean_num_ext(episode_num_ext: str) -> str:
        episode_num_ext.lower()
        if episode_num_ext[1] != 'e':
            episode_num_ext = '-e' + episode_num_ext[1:]

        return episode_num_ext

    @staticmethod
    def parse_episode_match(episode_match: re.Match, season: str) -> str:
        groups = episode_match.groupdict()
        episode_num = groups['episode'].lower().replace(' ', '')
        season_num = groups['season_num']

        season = 's' + season_num.zfill(2) if season_num else season

        episode_num = groups['episode_num'].lower()

        episode_num_ext = groups['episode_num_ext']
        episode_num_ext = (NameCleaner.clean_num_ext(episode_num_ext)
                           if episode_num_ext
                           else '')

        part_num = (groups['part_num'].lower().replace('part', 'pt')
                    if groups['part_num']
                    else '')

        episode_num = episode_num.zfill(2)

        episode = season + 'e' + episode_num + episode_num_ext + part_num

        return episode
