import os


EMBIT_ROOT = '../libs/common/embit/src'
EMBIT_MODULES = []
for root, dirs, files in os.walk(EMBIT_ROOT):
    sorted_dirs = []
    for dirname in sorted(dirs):
        if not (
            os.path.relpath(root, EMBIT_ROOT) == 'embit' and dirname == 'util'
        ):
            sorted_dirs.append(dirname)
    dirs[:] = sorted_dirs
    for filename in sorted(files):
        if filename.endswith('.py'):
            path = os.path.relpath(os.path.join(root, filename), EMBIT_ROOT)
            EMBIT_MODULES.append(path.replace(os.sep, '/'))

# embit/util contains CPython-only backends; firmware uses the C usermods.
freeze(EMBIT_ROOT, tuple(EMBIT_MODULES))
