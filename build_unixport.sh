#!/bin/bash
# mpy cross-compiler
make -C micropython/mpy-cross
# unixport
make -C micropython/ports/unix submodules
make -C micropython/ports/unix USER_C_MODULES=../../../usermods FROZEN_MANIFEST=../../../manifest_unixport.py
cp micropython/ports/unix/micropython micropython_unix
