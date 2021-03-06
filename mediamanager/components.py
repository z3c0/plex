import os
import re
import shutil as sh
import configparser as cfg
import concurrent.futures

from mediamanager.subcomponents import (Output, FileMover,
                                        Constants, NameCleaner)

config = cfg.ConfigParser()
config.read('media.cfg')


class MovieMover(FileMover):
    src_path = config['movies']['src_path'].replace('\\', '/')
    stg_path = config['movies']['stg_path'].replace('\\', '/')
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
    def run_threads(changes):
        def move_files_thread(old_path, new_path):
            file_name = new_path.split("/")[-1]
            old_name = old_path.split("/")[-1]

            Output.log.message(f'[MOVE] {file_name} ({old_name})')
            MovieMover.move(old_path, new_path)
            Output.log.message(f'[DONE] {file_name}')

            return new_path

        results = list()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            file_move_futures = (executor.submit(move_files_thread, old, new)
                                 for old, new in changes)

            for future in concurrent.futures.as_completed(file_move_futures):
                try:
                    result = future.result()
                    results.append(result)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    Output.log.message(e)
                    MovieMover.remove_files((tgt for _, tgt in changes))

        return results

    @staticmethod
    def process_manifest(changes: list) -> list:
        manifest = list()

        Output.log.header('processing manifest')

        for old_path, new_name in changes:
            new_path = MovieMover.stg_path + '/' + new_name
            target_path = MovieMover.tgt_path + '/' + new_name

            # if file exists on target or was already staged, skip it
            if os.path.isfile(target_path) or os.path.isfile(new_path):
                continue

            manifest.append((old_path, new_path))

        if len(manifest) == 0:
            Output.log.header('no changes found')
        else:
            Output.log.header('deployment manifest')
            for idx, (_, new_path) in enumerate(manifest):
                Output.log.message(f'[{str(idx).zfill(2)}] {new_path}')
            Output.log.divider()

        return manifest

    @staticmethod
    def move_files_to_target():
        results = list()
        for root, _, files in os.walk(MovieMover.stg_path):
            root = root.replace('\\', '/')
            for file in files:
                current_path = root + '/' + file
                stg_path_with_tgt = (MovieMover.stg_path, MovieMover.tgt_path)
                new_path = current_path.replace(*stg_path_with_tgt)

                try:
                    os.rename(current_path, new_path)
                    results.append(new_path)
                except PermissionError:
                    continue

        return results

    @staticmethod
    def clear_stage():
        sh.rmtree(MovieMover.stg_path)
        os.mkdir(MovieMover.stg_path)

    @staticmethod
    def move_files(changes: list):
        """
            changes is a list of 2-tuples
            changes[n][0] contains the path of the file to be moved
            changes[n][1] contains the desired name of the file
        """
        changes = sorted(changes, key=lambda n: n[1])

        manifest = MovieMover.process_manifest(changes)
        if len(manifest) == 0:
            Output.log.message('no changes found')
            return

        Output.log.message(f'{len(manifest)} movies found')

        stage_results = MovieMover.run_threads(manifest)
        Output.log.message(f'{len(stage_results)} movies moved to stage')

        target_results = MovieMover.move_files_to_target()
        Output.log.message(f'{len(target_results)} movies moved to target')

        if len(stage_results) == len(target_results):
            MovieMover.clear_stage()
            Output.log.header('deployment complete')

        elif len(stage_results) > len(target_results):
            missed_files = set(stage_results) | set(target_results)
            error_count = len(missed_files)
            Output.log.message(f'deployment failed for {error_count} files')
            for idx, file in enumerate(missed_files):
                Output.log.message(f'[{str(idx).zfill(2)}]: {file}')

        else:
            # not expected to ever run, but just in case
            extra_files = set(target_results) | set(stage_results)
            extra_count = len(extra_files)
            Output.log.message(f'deployment complete (w/{extra_count} extras)')
            for idx, file in enumerate(extra_files):
                Output.log.message(f'[{str(idx).zfill(2)}]: {file}')

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
    stg_path = config['tv']['stg_path'].replace('\\', '/')
    tgt_path = config['tv']['tgt_path'].replace('\\', '/')

    move = sh.copyfile

    overwrite = False

    @staticmethod
    def list_tv_shows_on_source():
        return os.listdir(TvMover.src_path)

    @staticmethod
    def list_tv_shows_on_target():
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
        try:
            os.makedirs(f'{TvMover.stg_path}/{tv_show_name}')
        except FileExistsError:
            pass

        try:
            os.makedirs(f'{TvMover.tgt_path}/{tv_show_name}')
        except FileExistsError:
            pass

    @staticmethod
    def allocate_space_for_season(tv_show_name: str, season: str):
        try:
            os.makedirs(f'{TvMover.stg_path}/{tv_show_name}/{season}')
        except FileExistsError:
            pass

        try:
            os.makedirs(f'{TvMover.tgt_path}/{tv_show_name}/{season}')
        except FileExistsError:
            pass

    @staticmethod
    def create_specials_folder(tv_show_name: str):
        try:
            os.makedirs(f'{TvMover.stg_path}/{tv_show_name}/s00')
        except FileExistsError:
            pass

        try:
            os.makedirs(f'{TvMover.tgt_path}/{tv_show_name}/s00')
        except FileExistsError:
            pass

    @staticmethod
    def clear_stage(tv_show: str):
        sh.rmtree(TvMover.stg_path + '/' + tv_show)

    @staticmethod
    def paths_are_equal(old_path: str, new_path: str) -> bool:
        return os.path.normpath(old_path) == os.path.normpath(new_path)

    @staticmethod
    def set_overwrite(overwrite):
        TvMover.overwrite = overwrite

    @staticmethod
    def set_file_operation(path):
        if TvMover.tgt_path == os.path.normpath(path):
            TvMover.move = os.rename
        else:
            TvMover.move = sh.copyfile

    @staticmethod
    def remove_files(paths):
        for path in paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                continue

    @staticmethod
    def move_tv_shows(tv_shows: list):
        for tv_show in tv_shows:
            episodes, specials = TvMover.clean_tv_show(tv_show)

            if len(episodes) == 0 and len(specials) == 0:
                continue

            Output.log.header(tv_show)

            if len(episodes) > 0:
                TvMover.move_files_to_stage(episodes)

            if len(specials) > 0:
                TvMover.create_specials_folder(tv_show)
                TvMover.move_specials(specials)

            TvMover.move_files_to_target()
            TvMover.clear_stage(tv_show)

    @staticmethod
    def run_threads(changes):
        def move_files_thread(old_path, new_path):
            target_path = new_path.replace(TvMover.stg_path, TvMover.tgt_path)

            # if file exists on target and overwriting is disabled, skip it
            if not TvMover.overwrite and os.path.isfile(target_path):
                return None

            file_name = new_path.split("/")[-1]

            old_path = os.path.normpath(old_path)
            new_path = os.path.normpath(new_path)

            Output.log.message(f'[STAGE] {file_name}',
                               f'|- src: {old_path}',
                               f'|- tgt: {new_path}')

            TvMover.move(old_path, new_path)
            Output.log.message(f'[DONE] {file_name}')

            return new_path

        results = list()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            file_move_futures = (executor.submit(move_files_thread, old, new)
                                 for old, new in changes)

            for future in concurrent.futures.as_completed(file_move_futures):
                try:
                    result = future.result()

                    if result is None:
                        continue

                    results.append(result)

                    if len(results) % 5 == 0:
                        Output.log.message('checkpoint reached')
                        TvMover.move_files_to_target()

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    Output.log.message(e)
                    TvMover.remove_files((tgt for _, tgt in changes))

        return results

    @staticmethod
    def move_files_to_target():
        for root, _, files in os.walk(TvMover.stg_path):
            root = root.replace('\\', '/')
            for file in files:
                current_path = root + '/' + file
                stg_path_with_tgt_path = (TvMover.stg_path, TvMover.tgt_path)
                new_path = current_path.replace(*stg_path_with_tgt_path)

                Output.log.message(f'[FINISH] {file}',
                                   f'|- stg: {current_path}',
                                   f'|- tgt: {new_path}\n')

                os.rename(current_path, new_path)

    @staticmethod
    def move_files_to_stage(changes):
        Output.log.message(f'{len(changes)} episodes found')
        results = TvMover.run_threads(changes)

        if len(results) > 0:
            Output.log.message(f'{len(results)} episodes moved to stage')
        else:
            Output.log.message('no changes')

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

            except KeyboardInterrupt:
                raise
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

        for root, season, episode in tv_show:
            old_episode_name = episode

            # skip hidden files
            if episode[0] == '.' or not re.match(r's\d+', season):
                continue

            # attempt to find the season number from the episode file.
            # if not found persist with the number found from the season folder
            season_num = NameCleaner.get_season_num_from_episode(episode)
            if season_num is not None and season_num != season:
                season = season_num

            # create a folder for the season on the stage and the target
            TvMover.allocate_space_for_season(tv_show_name, season)

            episode_match = re.search(Constants.Tv.EPISODE_REGEX, episode)
            episode_ext_match = re.search(r'^.+\.([a-z0-9]{2,4})$', episode)

            # if no extension can be determined, move on
            if not episode_ext_match:
                continue

            episode_ext = episode_ext_match.group(1).lower()

            valid_extensions = (Constants.PREFERRED_VIDEO_EXTENSIONS
                                .union(Constants.OTHER_VIDEO_EXTENSIONS)
                                .union(Constants.SUBTITLE_EXTENSIONS))

            # if an extension is found, but is not a valid extension, move on
            if episode_ext not in valid_extensions:
                continue

            # if no episode number can be found, move it to s00
            if not episode_match:
                new_name = NameCleaner.name_special_file(episode)

                old_path = root + '/' + episode
                new_path = f'{TvMover.stg_path}/{tv_show_name}/s00/{new_name}'

                odd_names.append((old_path, new_path))
                continue

            # if an episode number was found, finalize the name changes to
            # {stage directory}/{tv show name}/sXX/sXXeXX.{extension}"
            episode = NameCleaner.parse_episode_match(episode_match, season)

            new_path = (f'{TvMover.stg_path}/{tv_show_name}/{season}/'
                        f'{episode}.{episode_ext}')
            old_path = root + '/' + old_episode_name

            if not TvMover.paths_are_equal(old_path, new_path):
                changes.append((old_path, new_path))

        return changes, odd_names
