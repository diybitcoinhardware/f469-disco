/**
 * @file modSDL.c
 * @brief MicroPython module that wires LVGL v9 to the built-in SDL display &
 * input drivers.
 *
 * This module provides a tiny Python API (`SDL.init()`,
 * `SDL.enable_autoupdate()`, etc.) that creates an SDL window and registers
 * mouse/mousewheel/keyboard input devices via LVGL’s first-party SDL drivers
 * (v9.x). It also runs a background tick thread (or an Emscripten main loop)
 * that keeps LVGL time and schedules `lv_timer_handler()` to the MicroPython VM
 * thread when auto-update is enabled.
 *
 * @note Call `lv.init()` from Python before using this module.
 * @note This file intentionally contains no legacy v6 callbacks (e.g.
 * `monitor_flush`, `mouse_read`). The SDL drivers handle those internally in
 * LVGL v9.
 */

#define SDL_MAIN_HANDLED

#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <stdio.h>

#include <SDL2/SDL.h>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif

#include "py/obj.h"
#include "py/runtime.h"
#include "py/mphal.h"
#include "py/objstr.h"

#include "lvgl.h"

/* LVGL v9 built-in SDL drivers (path may vary by tree layout) */
#include "lvgl/src/drivers/sdl/lv_sdl_window.h"
#include "lvgl/src/drivers/sdl/lv_sdl_mouse.h"
#include "lvgl/src/drivers/sdl/lv_sdl_mousewheel.h"
#include "lvgl/src/drivers/sdl/lv_sdl_keyboard.h"

/* Portable atomics (fallback to volatile if C11 atomics unavailable) */
#if !defined(__STDC_NO_ATOMICS__) && (__STDC_VERSION__ >= 201112L)
#include <stdatomic.h>
#define ATOMIC_BOOL atomic_bool
#define ATOMIC_LOAD(ptr) atomic_load_explicit((ptr), memory_order_acquire)
#define ATOMIC_STORE(ptr, val) \
  atomic_store_explicit((ptr), (val), memory_order_release)
#define ATOMIC_INIT_FALSE ATOMIC_VAR_INIT(false)
#define ATOMIC_INIT_TRUE ATOMIC_VAR_INIT(true)
#else
typedef volatile bool ATOMIC_BOOL;
#define ATOMIC_LOAD(ptr) (*(ptr))
#define ATOMIC_STORE(ptr, val) (*(ptr) = (val))
#define ATOMIC_INIT_FALSE false
#define ATOMIC_INIT_TRUE true
#endif

/**
 * @def LVGL_SDL_TICK_MS
 * @brief Sleep quantum (in milliseconds) for the background tick thread.
 *
 * When auto-update is enabled, the tick thread sleeps for this period and then
 * advances LVGL time by the elapsed amount. Smaller values give smoother
 * updates at the cost of more wakeups.
 */
#ifndef LVGL_SDL_TICK_MS
#define LVGL_SDL_TICK_MS 5 /**< Default tick thread sleep, in ms. */
#endif

/* -------------------------------------------------------------------------- */
/*                              Module state                                  */
/* -------------------------------------------------------------------------- */

/** LVGL display handle created by the SDL window driver. */
static lv_display_t *s_disp = NULL;
/** LVGL mouse input device created by the SDL driver (optional). */
static lv_indev_t *s_mouse = NULL;
/** LVGL mouse wheel input device created by the SDL driver (optional). */
static lv_indev_t *s_wheel = NULL;
/** LVGL keyboard input device created by the SDL driver (optional). */
static lv_indev_t *s_kbd = NULL;

/** Whether the module is currently running (window alive, tick thread loop). */
static ATOMIC_BOOL s_running = ATOMIC_INIT_FALSE;
/** Whether auto-update is enabled (tick thread schedules lv_timer_handler()).
 */
static ATOMIC_BOOL s_autoupdate = ATOMIC_INIT_FALSE;
/** Whether a scheduler callback is already queued/pending. */
static ATOMIC_BOOL s_sched_pending = ATOMIC_INIT_FALSE;

#ifndef __EMSCRIPTEN__
/** Background SDL thread that advances LVGL time and schedules the handler. */
static SDL_Thread *s_tick_thread = NULL;
#else
static bool s_main_loop_set = false;
#endif

/* -------------------------------------------------------------------------- */
/*                     MicroPython scheduled callback                         */
/* -------------------------------------------------------------------------- */

/**
 * @brief MicroPython-scheduled callback that runs on the VM thread.
 *
 * Schedules and executes LVGL’s main handler (`lv_timer_handler()`).
 * This ensures all LVGL task processing and rendering happens on the same
 * thread as the MicroPython VM, avoiding interpreter reentrancy issues.
 *
 * @param arg Unused (MicroPython requires a single positional parameter).
 * @return `None` (MicroPython object).
 */
STATIC mp_obj_t mp_lv_timer_handler_cb(mp_obj_t arg) {
  (void)arg;
  lv_timer_handler();                    /* LVGL’s main handler in v9 */
  ATOMIC_STORE(&s_sched_pending, false); /* allow next schedule */
  return mp_const_none;
}
/* clang-format off */
STATIC MP_DEFINE_CONST_FUN_OBJ_1(mp_lv_timer_handler_cb_obj, mp_lv_timer_handler_cb);
/* clang-format on */

/* -------------------------------------------------------------------------- */
/*                               Helpers                                      */
/* -------------------------------------------------------------------------- */

/** Delete LVGL input devices and display (no thread interaction). */
STATIC void sdl_cleanup_devices_and_display(void) {
  if (s_mouse) {
    lv_indev_delete(s_mouse);
    s_mouse = NULL;
  }
  if (s_wheel) {
    lv_indev_delete(s_wheel);
    s_wheel = NULL;
  }
  if (s_kbd) {
    lv_indev_delete(s_kbd);
    s_kbd = NULL;
  }
  if (s_disp) {
    lv_display_delete(s_disp);
    s_disp = NULL;
  }
}

/** Stop background ticking and cleanup everything (safe across re-init/deinit).
 */
STATIC void sdl_stop_thread_and_cleanup(void) {
  ATOMIC_STORE(&s_autoupdate, false);
  ATOMIC_STORE(&s_running, false);
#ifndef __EMSCRIPTEN__
  if (s_tick_thread) {
    SDL_WaitThread(s_tick_thread, NULL);
    s_tick_thread = NULL;
  }
#else
  if (s_main_loop_set) {
    emscripten_cancel_main_loop();
    s_main_loop_set = false;
  }
#endif
  sdl_cleanup_devices_and_display();
  ATOMIC_STORE(&s_sched_pending, false);
}

/* Parse NUL-terminated title safely and enforce a length limit. */
STATIC const char *get_safe_title_and_check(mp_obj_t title_obj) {
  const char *title =
      mp_obj_str_get_str(title_obj); /* guaranteed NUL-terminated */
  size_t len = strlen(title);
  if (len > 256) {
    mp_raise_ValueError(MP_ERROR_TEXT("Window title too long"));
  }
  return title;
}

/* -------------------------------------------------------------------------- */
/*                       Background tick / main loop                          */
/* -------------------------------------------------------------------------- */

#ifndef __EMSCRIPTEN__

/**
 * @brief SDL background thread function that maintains LVGL time.
 *
 * The thread:
 *  - sleeps for @ref LVGL_SDL_TICK_MS,
 *  - computes elapsed milliseconds,
 *  - calls `lv_tick_inc(diff)`, and
 *  - if auto-update is on, schedules @ref mp_lv_timer_handler_cb on the
 *    MicroPython VM thread using `mp_sched_schedule()`.
 *
 * @param data Unused.
 * @return Always 0 when the thread exits.
 */
STATIC int tick_thread(void *data) {
  (void)data;
  Uint32 last = SDL_GetTicks();
  const Uint32 delay_ms = (LVGL_SDL_TICK_MS >= 1) ? LVGL_SDL_TICK_MS : 1;

  while (ATOMIC_LOAD(&s_running)) {
    SDL_Delay(delay_ms);

    if (ATOMIC_LOAD(&s_autoupdate)) {
      Uint32 now = SDL_GetTicks();
      Uint32 diff = now - last;
      last = now;
      lv_tick_inc(diff); /* v9 tick */

      /* Schedule handler to run on the MicroPython VM thread */
      if (!ATOMIC_LOAD(&s_sched_pending)) {
        /* Avoid overwhelming the scheduler queue; no return value assumed */
        mp_sched_schedule((mp_obj_t)&mp_lv_timer_handler_cb_obj, mp_const_none);
        ATOMIC_STORE(&s_sched_pending, true);
      }
    }
  }
  return 0;
}

#else  // !__EMSCRIPTEN__

/**
 * @brief Emscripten main loop hook that maintains LVGL time.
 *
 * Registered with `emscripten_set_main_loop()`. Calculates the elapsed time
 * since the previous invocation, advances LVGL with `lv_tick_inc(diff)` and,
 * if auto-update is enabled, schedules @ref mp_lv_timer_handler_cb on the
 * MicroPython VM thread.
 */
STATIC void em_main_loop(void) {
  static double last = 0.0;
  if (last == 0.0) last = emscripten_get_now();
  double now_d = emscripten_get_now();
  Uint32 diff = (Uint32)(now_d - last);
  last = now_d;

  if (ATOMIC_LOAD(&s_autoupdate)) {
    lv_tick_inc(diff);
    if (!ATOMIC_LOAD(&s_sched_pending)) {
      mp_sched_schedule((mp_obj_t)&mp_lv_timer_handler_cb_obj, mp_const_none);
      ATOMIC_STORE(&s_sched_pending, true);
    }
  }
}

#endif  // !__EMSCRIPTEN__

/* -------------------------------------------------------------------------- */
/*                           Public Python API                                */
/* -------------------------------------------------------------------------- */

/**
 * @brief Initialize the SDL window and optional input devices.
 *
 * @python
 * ```py
 * SDL.init(width, height, *, title=None, zoom=1.0,
 *          resizable=False, mouse=True, mousewheel=True, keyboard=False)
 * ```
 *
 * @details
 * Creates an LVGL display via `lv_sdl_window_create(width, height)`. Optionally
 * sets the title, zoom factor, and resizable flag on the window. Registers SDL-
 * backed input devices according to the boolean flags.
 *
 * If a previous window exists, it is deleted along with any input devices
 * before creating a new one.
 *
 * @warning You must call `lv.init()` (from the MicroPython LVGL binding) prior
 *          to calling this function.
 *
 * @param n_args Number of positional arguments (MicroPython internal).
 * @param pos_args Positional arguments array (MicroPython internal).
 * @param kw_args Keyword arguments map (MicroPython internal).
 * @return `None` (MicroPython object).
 */
STATIC mp_obj_t mp_sdl_init(size_t n_args, const mp_obj_t *pos_args,
                            mp_map_t *kw_args) {
  /* clang-format off */
    enum {
        ARG_width, ARG_height, ARG_title, ARG_zoom, ARG_resizable, ARG_mouse,
        ARG_mousewheel, ARG_keyboard
    };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_width,      MP_ARG_REQUIRED | MP_ARG_INT,  {.u_int=0} },
        { MP_QSTR_height,     MP_ARG_REQUIRED | MP_ARG_INT,  {.u_int=0} },
        { MP_QSTR_title,      MP_ARG_KW_ONLY  | MP_ARG_OBJ,  {.u_obj=MP_OBJ_NULL} },
        { MP_QSTR_zoom,       MP_ARG_KW_ONLY  | MP_ARG_OBJ,  {.u_obj=mp_const_none} },
        { MP_QSTR_resizable,  MP_ARG_KW_ONLY  | MP_ARG_BOOL, {.u_bool=false} },
        { MP_QSTR_mouse,      MP_ARG_KW_ONLY  | MP_ARG_BOOL, {.u_bool=true} },
        { MP_QSTR_mousewheel, MP_ARG_KW_ONLY  | MP_ARG_BOOL, {.u_bool=true} },
        { MP_QSTR_keyboard,   MP_ARG_KW_ONLY  | MP_ARG_BOOL, {.u_bool=false} },
    };
  /* clang-format on */
  mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
  mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args),
                   allowed_args, args);

  const int32_t w = (int32_t)args[ARG_width].u_int;
  const int32_t h = (int32_t)args[ARG_height].u_int;

  /* Validate dimensions early */
  if (w <= 0 || h <= 0 || w > 8192 || h > 8192) {
    mp_raise_ValueError(MP_ERROR_TEXT("bad width/height"));
  }

  /* Stop any previous run safely, including thread, then free LVGL objects */
  if (s_disp || s_mouse || s_wheel || s_kbd
#ifndef __EMSCRIPTEN__
      || s_tick_thread
#else
      || s_main_loop_set
#endif
  ) {
    sdl_stop_thread_and_cleanup();
  }

  /* SDL hints: best-effort. Do not treat as fatal to avoid trivial DoS. */
  (void)SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "nearest");
  (void)SDL_SetHint(SDL_HINT_VIDEO_HIGHDPI_DISABLED, "1");
  (void)SDL_SetHint(SDL_HINT_RENDER_VSYNC, "1");
  SDL_DisableScreenSaver();

  /* Create display */
  s_disp = lv_sdl_window_create(w, h);
  if (!s_disp) {
    sdl_stop_thread_and_cleanup();
    mp_raise_msg(&mp_type_RuntimeError,
                 MP_ERROR_TEXT("lv_sdl_window_create failed"));
  }

  /* Optional title (safe, NUL-terminated, bounded) */
  if (args[ARG_title].u_obj != MP_OBJ_NULL) {
    const char *title = get_safe_title_and_check(args[ARG_title].u_obj);
    lv_sdl_window_set_title(s_disp, title);
  }

  /* Optional zoom: validate & set */
  if (args[ARG_zoom].u_obj != mp_const_none) {
    float zoom = mp_obj_get_float(args[ARG_zoom].u_obj);
    if (!isfinite(zoom) || zoom < 0.0625f || zoom > 32.0f) {
      sdl_stop_thread_and_cleanup();
      mp_raise_ValueError(MP_ERROR_TEXT("bad zoom"));
    }
    lv_sdl_window_set_zoom(s_disp, zoom);
  }

  /* Optional resize behavior */
  lv_sdl_window_set_resizeable(s_disp, args[ARG_resizable].u_bool);

  /* Input devices; on failure, cleanup via helper and raise */
  if (args[ARG_mouse].u_bool) {
    s_mouse = lv_sdl_mouse_create();
    if (!s_mouse) {
      sdl_stop_thread_and_cleanup();
      mp_raise_msg(&mp_type_RuntimeError,
                   MP_ERROR_TEXT("lv_sdl_mouse_create failed"));
    }
  }
  if (args[ARG_mousewheel].u_bool) {
    s_wheel = lv_sdl_mousewheel_create();
    if (!s_wheel) {
      sdl_stop_thread_and_cleanup();
      mp_raise_msg(&mp_type_RuntimeError,
                   MP_ERROR_TEXT("lv_sdl_mousewheel_create failed"));
    }
  }
  if (args[ARG_keyboard].u_bool) {
    s_kbd = lv_sdl_keyboard_create();
    if (!s_kbd) {
      sdl_stop_thread_and_cleanup();
      mp_raise_msg(&mp_type_RuntimeError,
                   MP_ERROR_TEXT("lv_sdl_keyboard_create failed"));
    }
  }

  /* Start ticking */
  ATOMIC_STORE(&s_running, true);
  ATOMIC_STORE(&s_sched_pending, false);

#ifdef __EMSCRIPTEN__
  /* Only disable text/key events if keyboard=False */
  if (!args[ARG_keyboard].u_bool) {
    SDL_EventState(SDL_TEXTINPUT, SDL_DISABLE);
    SDL_EventState(SDL_KEYDOWN, SDL_DISABLE);
    SDL_EventState(SDL_KEYUP, SDL_DISABLE);
  }
  if (!s_main_loop_set) {
    emscripten_set_main_loop(em_main_loop, 0, 0);
    s_main_loop_set = true;
  }
#else
  if (!s_tick_thread) {
    s_tick_thread = SDL_CreateThread(tick_thread, "lvgl_tick", NULL);
    if (!s_tick_thread) {
      sdl_stop_thread_and_cleanup();
      mp_raise_msg(&mp_type_RuntimeError,
                   MP_ERROR_TEXT("SDL_CreateThread failed"));
    }
  }
#endif

  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(mp_sdl_init_obj, 0, mp_sdl_init);

/** Shut down the SDL window and input devices and stop background updates. */
STATIC mp_obj_t mp_sdl_deinit(void) {
  sdl_stop_thread_and_cleanup();
  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(mp_sdl_deinit_obj, mp_sdl_deinit);

/** Enable automatic LVGL updates (tick & lv_timer_handler() scheduling). */
STATIC mp_obj_t mp_sdl_enable_autoupdate(void) {
  ATOMIC_STORE(&s_autoupdate, true);
  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(mp_sdl_enable_autoupdate_obj,
                                 mp_sdl_enable_autoupdate);

/** Disable automatic LVGL updates. */
STATIC mp_obj_t mp_sdl_disable_autoupdate(void) {
  ATOMIC_STORE(&s_autoupdate, false);
  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(mp_sdl_disable_autoupdate_obj,
                                 mp_sdl_disable_autoupdate);

/** Set the SDL window zoom factor. */
STATIC mp_obj_t mp_sdl_set_zoom(mp_obj_t zoom_in) {
  if (!s_disp) {
    mp_raise_ValueError(MP_ERROR_TEXT("init() first"));
  }
  float zoom = mp_obj_get_float(zoom_in);
  if (!isfinite(zoom) || zoom < 0.0625f || zoom > 32.0f) {
    mp_raise_ValueError(MP_ERROR_TEXT("bad zoom"));
  }
  lv_sdl_window_set_zoom(s_disp, zoom);
  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(mp_sdl_set_zoom_obj, mp_sdl_set_zoom);

/** Set the SDL window title (safe NUL-terminated). */
STATIC mp_obj_t mp_sdl_set_title(mp_obj_t title_in) {
  if (!s_disp) {
    mp_raise_ValueError(MP_ERROR_TEXT("init() first"));
  }
  const char *title = get_safe_title_and_check(title_in);
  lv_sdl_window_set_title(s_disp, title);
  return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(mp_sdl_set_title_obj, mp_sdl_set_title);

/** Toggle the SDL window's resizable flag. */
STATIC mp_obj_t mp_sdl_set_resizable(mp_obj_t val_in) {
  if (!s_disp) {
    mp_raise_ValueError(MP_ERROR_TEXT("init() first"));
  }
  lv_sdl_window_set_resizeable(s_disp, mp_obj_is_true(val_in));
  return mp_const_none;
}
/* clang-format off */
STATIC MP_DEFINE_CONST_FUN_OBJ_1(mp_sdl_set_resizable_obj, mp_sdl_set_resizable);
/* clang-format on */

/**
 * @brief Take a screenshot and write directly to file (bypasses Python heap).
 *
 * Uses SDL_RenderReadPixels to capture, writes RGB565 data to file.
 * This avoids MicroPython heap allocation for large buffers.
 *
 * @param filename Path to write the raw RGB565 data
 * @return tuple(width, height, filename) or raises RuntimeError on failure.
 */
STATIC mp_obj_t mp_sdl_screenshot(mp_obj_t filename_obj) {
  if (!s_disp) {
    mp_raise_ValueError(MP_ERROR_TEXT("init() first"));
  }

  const char *filename = mp_obj_str_get_str(filename_obj);

  SDL_Renderer *renderer = (SDL_Renderer *)lv_sdl_window_get_renderer(s_disp);
  if (!renderer) {
    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("no renderer"));
  }

  int32_t w = lv_display_get_horizontal_resolution(s_disp);
  int32_t h = lv_display_get_vertical_resolution(s_disp);

  if (w <= 0 || h <= 0 || w > 8192 || h > 8192) {
    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("bad dimensions"));
  }

  /* Open output file */
  FILE *f = fopen(filename, "wb");
  if (!f) {
    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("cannot open file"));
  }

  /* Process in row chunks to minimize memory usage */
  int32_t chunk_rows = 32;  /* Process 32 rows at a time */
  size_t rgba_chunk_size = (size_t)w * chunk_rows * 4;
  size_t rgb565_chunk_size = (size_t)w * chunk_rows * 2;

  uint8_t *rgba_buf = (uint8_t *)malloc(rgba_chunk_size);
  uint8_t *rgb565_buf = (uint8_t *)malloc(rgb565_chunk_size);

  if (!rgba_buf || !rgb565_buf) {
    if (rgba_buf) free(rgba_buf);
    if (rgb565_buf) free(rgb565_buf);
    fclose(f);
    mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("malloc chunk failed"));
  }

  /* Process screen in chunks */
  for (int32_t y = 0; y < h; y += chunk_rows) {
    int32_t rows = (y + chunk_rows > h) ? (h - y) : chunk_rows;
    SDL_Rect rect = {0, y, w, rows};

    if (SDL_RenderReadPixels(renderer, &rect, SDL_PIXELFORMAT_RGBA8888,
                             rgba_buf, w * 4) != 0) {
      free(rgba_buf);
      free(rgb565_buf);
      fclose(f);
      mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("SDL_RenderReadPixels failed"));
    }

    /* Convert RGBA8888 to RGB565 */
    for (int32_t i = 0; i < w * rows; i++) {
      uint8_t r = rgba_buf[i * 4 + 0];
      uint8_t g = rgba_buf[i * 4 + 1];
      uint8_t b = rgba_buf[i * 4 + 2];
      uint16_t rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
      rgb565_buf[i * 2 + 0] = rgb565 & 0xFF;
      rgb565_buf[i * 2 + 1] = (rgb565 >> 8) & 0xFF;
    }

    /* Write chunk to file */
    fwrite(rgb565_buf, 1, w * rows * 2, f);
  }

  free(rgba_buf);
  free(rgb565_buf);
  fclose(f);

  /* Return tuple (width, height, filename) */
  mp_obj_t tuple[3] = {
    mp_obj_new_int(w),
    mp_obj_new_int(h),
    filename_obj
  };
  return mp_obj_new_tuple(3, tuple);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(mp_sdl_screenshot_obj, mp_sdl_screenshot);

/* -------------------------------------------------------------------------- */
/*                               Module table */
/* -------------------------------------------------------------------------- */

/* clang-format off */
STATIC const mp_rom_map_elem_t sdl_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__),            MP_ROM_QSTR(MP_QSTR_SDL) },
    { MP_ROM_QSTR(MP_QSTR_init),                MP_ROM_PTR(&mp_sdl_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_deinit),              MP_ROM_PTR(&mp_sdl_deinit_obj) },
    { MP_ROM_QSTR(MP_QSTR_enable_autoupdate),   MP_ROM_PTR(&mp_sdl_enable_autoupdate_obj) },
    { MP_ROM_QSTR(MP_QSTR_disable_autoupdate),  MP_ROM_PTR(&mp_sdl_disable_autoupdate_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_zoom),            MP_ROM_PTR(&mp_sdl_set_zoom_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_title),           MP_ROM_PTR(&mp_sdl_set_title_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_resizable),       MP_ROM_PTR(&mp_sdl_set_resizable_obj) },
    { MP_ROM_QSTR(MP_QSTR_screenshot),          MP_ROM_PTR(&mp_sdl_screenshot_obj) },
};
/* clang-format on */

STATIC MP_DEFINE_CONST_DICT(mp_module_SDL_globals, sdl_globals_table);

const mp_obj_module_t mp_module_SDL = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&mp_module_SDL_globals};
