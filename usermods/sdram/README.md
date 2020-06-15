# SDRAM as block device

For temporary storage. Pretty large - 16 Mb minus 2x display framebuffers.

Usage:

```py
import sdram
sdram.init()

bdev = RAMDevice(512)
os.VfsFat.mkfs(bdev)
os.mount(bdev, '/ramdisk')
# now use it as usual - write / read files folders etc
```