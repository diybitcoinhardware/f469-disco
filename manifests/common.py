import os


COMMON_ROOT = '../libs/common'
COMMON_MODULES = []
for root, dirs, files in os.walk(COMMON_ROOT):
    sorted_dirs = []
    for dirname in sorted(dirs):
        if not (root == COMMON_ROOT and dirname == 'embit'):
            sorted_dirs.append(dirname)
    dirs[:] = sorted_dirs
    for filename in sorted(files):
        if filename.endswith('.py'):
            path = os.path.relpath(os.path.join(root, filename), COMMON_ROOT)
            COMMON_MODULES.append(path.replace(os.sep, '/'))

freeze(COMMON_ROOT, tuple(COMMON_MODULES))

include('embit.py')
