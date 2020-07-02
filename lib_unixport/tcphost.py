import socket

# mimics API of pyb.USB_VCP / pyb.UART etc
class TCPHost:
    def __init__(self, port=8789):
        self.port = port
        self.socket = socket.socket()
        ai = socket.getaddrinfo("0.0.0.0", port)
        addr = ai[0][-1]
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(addr)
        self.socket.listen(5)
        self.socket.setblocking(False)
        self.client = None
        self.buf = b''
        self._check()

    def isconnected(self):
        self._check()
        return (self.client is not None)

    def any(self):
        self._check()
        return len(self.buf)

    # `last` argument is used to avoid circular recursion
    def _check(self, last=False):
        if self.client is not None:
            # check if EAGAIN on recv - still connected
            # if b'' is returned on read - disconnected
            try:
                # large enough to read all
                b = self.client.recv(10000)
                if len(b) == 0:
                    self.client.close()
                    self.client = None
                    # try to check connections if this one is dead
                    if not last:
                        self._check()
                else:
                    self.buf += b
            except OSError as e:
                if "EAGAIN" not in str(e) and "ECONNRESET" not in str(e):
                    raise e
        else:
            # check if got connected
            try:
                res = self.socket.accept()
                self.client = res[0]
                self._check(last=True)
            except OSError as e:
                if "EAGAIN" not in str(e):
                    raise e

    def read(self, nbytes=None):
        self._check()
        if nbytes is None or nbytes >= len(self.buf):
            buf = self.buf
            self.buf = b''
        else:
            buf = self.buf[:nbytes]
            self.buf = self.buf[nbytes:]
        # uart.read() returns None if there is nothing
        if len(buf)==0:
            return None
        return buf

    def readinto(self, data):
        try:
            d = self.read(len(data))
            for i in range(len(d)):
                data[i] = d[i]
            return len(d)
        except:
            return 0

    def write(self, data):
        try:
            return self.client.write(data)
        except:
            return 0

if __name__ == '__main__':
    tcphost = TCPHost()
