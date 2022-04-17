# Media Manager

To use this library, create a .cfg file at the root of the project, like so:

```cfg
[tv]
src_path=A:/source/directory
tgt_path=B:/target/directory

[movies]
src_path=A:/source/directory
tgt_path=B:/target/directory
```

The default config file name is `media.cfg`. This can be modified in the `Constants` class of the `mediamanager/subcomponents.py` file.

To process movie files, run `python clean_movies.py`.

To process tv files, run `python clean_tv.py`
