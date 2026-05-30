#!/usr/bin/env bash

################################################################################
# 🛠️  generate-bindings.sh
# Generates MicroPython bindings for udisplay_f469 using lv_binding_micropython
#
# Run from: usermods/udisplay_f469
################################################################################

set -e
set -o pipefail

# Repository URL
LV_BINDING_REPO_URL="https://github.com/lvgl/lv_binding_micropython.git"

# Temporary directory variable
TMP_DIR="tmp_binding_gen"

# Paths relative to script location
LVGL_INCLUDE="../../lvgl"
LVGL_HEADER="$LVGL_INCLUDE/lvgl.h"
FAKE_LIBC_INCLUDE="pycparser/utils/fake_libc_include"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Emojis
CHECK="✅"
INFO="ℹ️ "
ERROR="❌"

echo -e "${CYAN}${INFO} Checking prerequisites...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}${ERROR} Python3 is not installed.${NC}"; exit 1; }
command -v git >/dev/null 2>&1 || { echo -e "${RED}${ERROR} Git is not installed.${NC}"; exit 1; }
command -v gcc >/dev/null 2>&1 || { echo -e "${RED}${ERROR} GCC is not installed.${NC}"; exit 1; }
echo -e "${GREEN}${CHECK} Prerequisites OK.${NC}"

echo -e "${CYAN}${INFO} Creating temporary directory ${TMP_DIR}...${NC}"
rm -rf "${TMP_DIR}"
mkdir "${TMP_DIR}"
cd "${TMP_DIR}"

echo -e "${CYAN}${INFO} Creating Python venv...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${CYAN}${INFO} Cloning lv_binding_micropython without submodules...${NC}"
git clone --depth=1 --no-recurse-submodules "${LV_BINDING_REPO_URL}"

cd lv_binding_micropython

echo -e "${CYAN}${INFO} Initializing pycparser submodule...${NC}"
git submodule update --init pycparser

echo -e "${CYAN}${INFO} Installing Python requirements...${NC}"
pip install --upgrade pip >/dev/null
pip install pycparser cffi >/dev/null

echo -e "${CYAN}${INFO} Generating MicroPython bindings...${NC}"

python gen/gen_mpy.py \
  -M lvgl \
  -MP lv \
  -I$LVGL_INCLUDE \
  -I$FAKE_LIBC_INCLUDE \
  $LVGL_HEADER \
  $CUSTOM_HEADER > tmp_bindings.c

# Fix include paths in generated file
sed -e 's|#include "../../lvgl/|#include "lvgl/|g' \
    tmp_bindings.c > ../../lv_mpy.c
rm tmp_bindings.c

echo -e "${GREEN}${CHECK} Binding generation completed.${NC}"

echo -e "${CYAN}${INFO} Deactivating venv...${NC}"
deactivate

cd ../..

echo -e "${CYAN}${INFO} Cleaning up ${TMP_DIR}...${NC}"
rm -rf "${TMP_DIR}"

echo -e "${GREEN}${CHECK} All done.${NC}"
