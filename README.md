# Media Manager

To use this library, create a .cfg file at the root of the project, like so:

```cfg
[tv]
src_path=A:/source/directory
tgt_path=B:/target/directory
thread_count=8

[movies]
src_path=A:/source/directory
tgt_path=B:/target/directory
thread_count=8
```

To process movie files, run `python clean_movies.py`.

To process tv files, run `python clean_tv.py`
