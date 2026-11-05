#!/usr/bin/env bash
set -euo pipefail
# Use the same configuration header and library as the caller's headless LVGL build.
: "${LVGL_ROOT:?Path to LVGL 9.3 source}"
: "${LVGL_CONFIG_DIR:?Directory containing lv_conf.h used for LVGL_LIBRARY}"
: "${LVGL_LIBRARY:?Path to the built liblvgl.a}"
ui_root=$(cd "$(dirname "$0")/../.." && pwd)
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
flags=(-DLV_CONF_INCLUDE_SIMPLE -I"$LVGL_CONFIG_DIR" -I"$LVGL_ROOT")
for size in 12 16; do
	cc "${flags[@]}" -c "$ui_root/generated/ui_320x240/ui_font_montserrat_${size}.c" -o "$build_dir/font${size}.o"
done
c++ -std=c++17 -Wall -Wextra -Werror -DVIEW_320x240 "${flags[@]}" \
	-I"$ui_root/include" -I"$ui_root/generated/ui_320x240" \
	"$ui_root/tests/control_center/test_control_center.cpp" \
	"$ui_root/source/graphics/TFT/ControlCenter.cpp" "$build_dir"/*.o "$LVGL_LIBRARY" -lm -o "$build_dir/tests"
"$build_dir/tests"
