import os
import re
import queue as q
import threading as thr
import shutil as sh
import configparser as cfg

from subcomponents import Output, FileMover, Constants, NameCleaner


config = cfg.ConfigParser()
config.read('plex.cfg')


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
        for _ in range(Constants.THREAD_COUNT):
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
            for _ in range(Constants.THREAD_COUNT):
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

        if len(manifest):
            Output.log.header('deployment manifest')
            for idx, (_, new_path) in enumerate(manifest):
                Output.log.message(f'[{str(idx).zfill(2)}] {new_path}')
            Output.log.divider()
        else:
            Output.log.header('no changes')

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

        queue = q.PriorityQueue(Constants.THREAD_COUNT)
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
                    Output.log.message(str(e))
                    errors.append((old_path, new_path))
                    raise
                finally:
                    queue.task_done()

        MovieMover.run_threads(queue, manifest, move_files_thread)

        Output.log.header('deployment complete')

    @staticmethod
    def search(all_files: list, preferred_only=False) -> list:
        video_files = list()
        subtitle_files = list()

        extensions = Constants.PREFERRED_VIDEO_EXTENSIONS
        other_extensions = Constants.OTHER_VIDEO_EXTENSIONS

        all_extensions = (extensions.union(other_extensions)
                          if not preferred_only
                          else extensions)

        extension = None
        extension_match = None

        for path, file in all_files:
            file = file.lower()
            extension_match = re.search(r'^(.+)\.([a-z0-9]{2,4})$', file)
            if not extension_match:
                continue

            name = extension_match.group(1)
            extension = extension_match.group(2)

            if extension in Constants.SUBTITLE_EXTENSIONS:
                subtitle_files.append((path, name, extension))

            if extension not in all_extensions:
                continue

            if file[0] == '.':
                continue

            if 'sample' in file:
                continue

            video_files.append((path, name, extension))

        return video_files, subtitle_files

    @staticmethod
    def process_new_titles(video_files: list, subtitle_files: list) -> list:
        name_changes = []

        for path, file, ext in video_files:
            new_name = NameCleaner.movie_name(file)

            if new_name == '.' + ext:
                continue

            sub_name = None
            for sub_path, sub_file, sub_ext in subtitle_files:
                if sub_file == file:
                    sub_name = sub_file + '.' + sub_ext
                    break

            name_changes.append((f'{path}/{file}.{ext}', f'{new_name}.{ext}'))

            if sub_name:
                new_sub_name = f'{new_name}.eng.{sub_ext}'
                name_changes.append((f'{sub_path}/{sub_name}', new_sub_name))

        return name_changes


class TvMover(FileMover):

    src_path = config['tv']['src_path'].replace('\\', '/')
    tgt_path = config['tv']['tgt_path'].replace('\\', '/')

    move = sh.copyfile

    overwrite = False

    @staticmethod
    def list_files_on_source():
        return os.listdir(TvMover.src_path)

    @staticmethod
    def list_files_on_target():
        return os.listdir(TvMover.tgt_path)

    @staticmethod
    def get_tv_show_files(tv_show_folder_name: str):
        tv_show_folder_name = f'{TvMover.src_path}/{tv_show_folder_name}'
        tv_show_folder = os.walk(tv_show_folder_name)

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
        if not os.path.exists(TvMover.tgt_path + '/' + tv_show_name):
            os.makedirs(TvMover.tgt_path + '/' + tv_show_name)

    @staticmethod
    def allocate_space_for_season(tv_show_name: str, season: str):
        season_path = f'{TvMover.tgt_path}/{tv_show_name}/{season}'
        if not os.path.exists(season_path):
            os.makedirs(season_path)

    @staticmethod
    def create_specials_folder(tv_show_name: str):
        season_zero_path = f'{TvMover.tgt_path}/{tv_show_name}/s00'
        if not os.path.exists(season_zero_path):
            os.makedirs(season_zero_path)

    @staticmethod
    def paths_are_equal(old_path: str, new_path: str) -> bool:
        return os.path.normpath(old_path) == os.path.normpath(new_path)

    @staticmethod
    def set_overwrite(overwrite):
        TvMover.overwrite = overwrite

    @staticmethod
    def set_file_operation(path):
        TvMover.move = \
            (os.rename if TvMover.tgt_path == os.path.normpath(path)
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
        for _ in range(Constants.THREAD_COUNT):
            thread = thr.Thread(target=func, daemon=True)
            thread.start()

        try:
            for idx, (old_path, new_path) in enumerate(changes):
                queue.put(((idx + 1) * -1, old_path, new_path))

            queue.join()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            Output.log.message(str(e))
            TvMover.remove_files((tgt for _, tgt in changes))

        finally:
            for _ in range(Constants.THREAD_COUNT):
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

                if not TvMover.overwrite and os.path.isfile(new_path):
                    Output.log.message(f'[SKIP] {new_path.split("/")[-1]}')
                    queue.task_done()
                    continue

                try:
                    file_name = new_path.split("/")[-1]
                    old_name = old_path.split("/")[-1]

                    Output.log.message(f'[MOVE] {file_name} ({old_name})')
                    TvMover.move(old_path, new_path)
                    Output.log.message(f'[DONE] {file_name}')

                except Exception as e:
                    Output.log.message(str(e))
                    errors.append((old_path, new_path))

                queue.task_done()

        TvMover.run_threads(queue, changes, move_files_thread)

        # clean-up half-processed files for re-attempting
        TvMover.remove_files((tgt for _, tgt in errors))

    @staticmethod
    def move_specials(odd_names):
        Output.log.message('moving oddly-named files to s00')
        for old_path, new_path in odd_names:
            try:
                file_name = new_path.split("/")[-1]
                old_name = old_path.split("/")[-1]

                Output.log.message(f'[MOVE] {file_name} ({old_name})')
                TvMover.move(old_path, new_path)
                Output.log.message(f'[DONE] {file_name}')
            except Exception as e:
                Output.log.message(str(e))
                continue

    @staticmethod
    def clean_tv_show(tv_show_name: str, path=None):
        path = path if path is not None else TvMover.src_path

        tv_show_name = NameCleaner.tv_show_name(tv_show_name)

        TvMover.set_file_operation(path)
        TvMover.allocate_space_for_show(tv_show_name)

        tv_show = TvMover.get_tv_show_files(tv_show_name)

        changes = []
        odd_names = []

        if len(tv_show):
            Output.log.header(tv_show_name)

        for root, season, episode in tv_show:
            old_episode_name = episode

            # skip hidden files
            if episode[0] == '.' or not re.match(r's\d+', season):
                continue

            season_num = NameCleaner.get_season_num_from_episode(episode)
            season = (season_num if season_num and season_num != season
                      else season)

            TvMover.allocate_space_for_season(tv_show_name, season)

            episode_match = re.search(Constants.Tv.EPISODE_REGEX, episode)
            episode_ext_match = re.search(r'^.+\.([a-z0-9]{2,4})$', episode)

            if not episode_ext_match:
                continue

            episode_ext = episode_ext_match.group(1).lower()

            valid_extensions = (Constants.PREFERRED_VIDEO_EXTENSIONS
                                .union(Constants.OTHER_VIDEO_EXTENSIONS)
                                .union(Constants.SUBTITLE_EXTENSIONS))

            if episode_ext not in valid_extensions:
                continue

            if not episode_match:
                new_name = NameCleaner.name_special_file(episode)

                old_path = root + '/' + episode
                new_path = f'{TvMover.tgt_path}/{tv_show_name}/s00/{new_name}'

                odd_names.append((old_path, new_path))
                continue

            episode = NameCleaner.parse_episode_match(episode_match, season)

            new_path = (f'{TvMover.tgt_path}/{tv_show_name}/{season}/'
                        f'{episode}.{episode_ext}')
            old_path = root + '/' + old_episode_name

            if not TvMover.paths_are_equal(old_path, new_path):
                changes.append((old_path, new_path))

        return changes, odd_names
