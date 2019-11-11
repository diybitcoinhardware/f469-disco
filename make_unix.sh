pushd micropython/ports/unix
make USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../usermods/udisplay_f469/manifest.py
cp ./micropython ../../../micropython_unix
popd
chmod +x ./micropython_unix
