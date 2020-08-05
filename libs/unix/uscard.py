"""
This module simulates uscard smart card module available on hardware
Instead of a real card it connects to the javacard simulator.
It expects the simulator to run on port 21111.

Simulation is not complete, but should provide everything 
required for normal functionality.
"""
import socket

class SmartcardException(Exception):
    pass

class CardConnectionException(SmartcardException):
    pass

class NoCardException(SmartcardException):
    pass

def enableDebug(*args, **kwargs):
    pass

class CardConnection:
    T1_protocol = 1
    T0_protocol = 2
    def __init__(self):
        self.s = None

    def isCardInserted(self):
        if self.s is not None:
            return True
        try:
            self.s = socket.socket()
            addr = socket.getaddrinfo('127.0.0.1', 21111)[0][-1]
            self.s.connect(addr)
            return True
        except:
            self.s = None
        return False

    def connect(self, protocol):
        if not self.isCardInserted():
            raise NoCardException("no card inserted")
        self.protocol = protocol

    def disconnect(self):
        pass

    def getATR(self):
        return b"simulator ATR"

    def transmit(self, data):
        if not self.isCardInserted():
            raise NoCardException("no card inserted")
        self.s.send(bytes(data))
        return self.s.recv(300)

class Reader:
    def __init__(self, *args, **kwargs):
        pass

    def createConnection(self):
        return CardConnection()
