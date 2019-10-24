# lvgl gui demo

you can run `demo_unixport.py` on a unix port of [lv_micropython](https://github.com/littlevgl/lv_micropython/).

It demostrates how to work with [littlevgl](https://littlevgl.com) from micropython.

It will show a small screen with a counter and two buttons.

## Mac notes

To compile unixport on mac and run it you need to edit a file

`lv_micropython/lib/lv_bindings/linux/modfb.c` 

It is not really used for this demo, but prevents micropython from compiling for linux.

See [`modfb.c`](./modfb.c) file in this folder.

