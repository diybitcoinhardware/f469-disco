# boilerplate for some classes in pyb module
# such that emulator still works fine
from micropython import const
from tcphost import TCPHost
from io import BytesIO


class CPU:
    A2 = "A2"
    A4 = "A4"
    G10 = "G10"
    C2 = "C2"
    C5 = "C5"


class Pin:
    IN = const(0)
    OUT = const(1)
    cpu = CPU
    # other values?
    def __init__(self, name, *args, **kwargs):
        self._name = name

    def on(self):
        print("Pin", self._name, "set to ON")

    def off(self):
        print("Pin", self._name, "set to OFF")


class UART(TCPHost):
    def __init__(self, name, *args, **kwargs):
        # port will be 5941 for YA
        port = int.from_bytes(name.encode(), "big")
        # find first available port, stop after 10 attempts
        for i in range(10):
            try:
                super().__init__(port)
                break
            except:
                port += 1
        print("Running TCP-UART on 127.0.0.1 port %d - connect with telnet" % port)

    def init(self, *args, **kwargs):
        pass

    def deinit(self, *args, **kwargs):
        pass


class USB_VCP(TCPHost):
    RTS = 1
    CTS = 2

    def __init__(self, *args, **kwargs):
        port = 8789
        # find first available port, stop after 10 attempts
        for i in range(10):
            try:
                super().__init__(port)
                break
            except:
                port += 1
        print("Running TCP-USB_VCP on 127.0.0.1 port %d - connect with telnet" % port)

    def init(self, *args, **kwargs):
        pass

    def any(self):
        # USB_VCP returns a bool here
        return super().any() > 0


class USB_HID:
    def __init__(self, *args, **kwargs):
        port = 8790
        self._host = TCPHost(port)
        print("Running TCP-USB_HID on 127.0.0.1 port %d - connect with telnet" % port)

    def recv(self, data, *, timeout=5000):
        """
        Receive data on the bus:
        can be an integer, which is the number of bytes to receive,
        or a mutable buffer, which will be filled with received bytes
        """
        # simulating weird behaviour of hid class
        # can receive only one packet at a time
        # rest is dropped
        chunk = self._host.read(64)
        if isinstance(data, int):
            return chunk[:data]
        else:
            l = min([len(chunk), len(data)])
            for i in range(l):
                data[i] = chunk[i]
            return l

    def send(self, data):
        # simulating weird behaviour of hid class
        # can send only exactly one packet
        # rest is dropped, smaller is dropped completely
        # returns len(data) no matter what...
        if len(data) < 64:
            return len(data)
        self._host.write(data[:64])
        return len(data)


_USB_MODE = None


def usb_mode(*args, **kwargs):
    global _USB_MODE
    if len(args) == 0:
        return _USB_MODE
    mode = args[0]
    _USB_MODE = mode
