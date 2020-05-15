# boilerplate for some classes in pyb module
# such that emulator still works fine
from micropython import const
from tcphost import TCPHost
from io import BytesIO

class Pin:
    IN = const(0)
    OUT = const(1)
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
        port = int.from_bytex(name.encode())
        super().__init__(port)
        print("Running TCP-UART on 127.0.0.1 port %d - connect with telnet" % port)

class USB_VCP(TCPHost):
    def __init__(self, *args, **kwargs):
        port = 8789
        super().__init__(port)
        print("Running TCP-USB_VCP on 127.0.0.1 port %d - connect with telnet" % port)

    def any(self):
        # USB_VCP returns a bool here
        return (super().any() > 0)

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
        if isinstance(data, int):
            return self._host.read(data)
        else:
            return self._host.readinto(data)

    def send(self, data):
        return self._host.write(data)