pushd micropython/ports/unix
make USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../usermods/udisplay_f469/manifest.py
popd
