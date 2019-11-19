pushd micropython/ports/unix
make USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_unixport.py
cp ./micropython ../../../micropython_unix
popd