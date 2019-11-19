#!/bin/bash
# mpy cross-compiler
pushd micropython/mpy-cross
make
popd
# unixport
pushd micropython/ports/unix
make submodules
make USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_unixport.py
cp ./micropython ../../../micropython_unix
popd