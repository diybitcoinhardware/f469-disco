from ipykernel.kernelbase import Kernel
import pexpect
import time

class MPYBinary:
    def __init__(self, path, timeout=0.1):
        self.proc = pexpect.spawn(path, timeout=timeout)

    def readlines(self):
        lines = []
        try:
            while True:
                line = self.proc.readline().decode('utf-8')
                if line.endswith("\r\n"):
                    line = line[:-2]
                lines.append(line)
        except:
            pass
        return lines

    def exec(self, code):
        if len(code.split("\n")) == 2:
            self.proc.write(code.encode("utf-8"))
            lines = [line for line in self.readlines() if not line.startswith(">>> ")]
            res = "\r\n".join(lines)
        else:
            self.proc.sendcontrol("E")
            self.proc.write(code.encode("utf-8"))
            self.proc.sendcontrol("D")
            lines = self.readlines()[2:]
            res = ""
            res = "\r\n".join([line for line in lines if not line.startswith("=== ")])
        return res

    def kill(self):
        self.proc.kill(9)
        time.sleep(0.1)

import serial
class MPYSerial:
    def __init__(self, port, baudrate=115200, timeout=2):
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.ser.read(self.ser.in_waiting)
        self.ser.write(b"\x04")
        time.sleep(0.1)
        self.timeout=timeout

    def readlines(self):
        res = b""
        t = time.time()
        while not res.endswith(b">>> "):
            res += self.ser.read(self.ser.in_waiting)#.decode("utf-8")
            if time.time() > t+self.timeout:
                break
        return (b">>> "+res).split(b"\r\n")

    def exec(self, code):
        if len(code.split("\n")) == 2:
            self.ser.write(code.encode("utf-8"))
            lines = [line for line in self.readlines() if not line.startswith(b">>> ")]
            res = b"\n".join(lines)
        else:
            self.ser.write(b"\r\x05")
            self.ser.write(code.encode("utf-8")+b"\r\n")
            self.ser.write(b"\r\x04")
            time.sleep(0.1)
            lines = self.readlines()[2:]
            res = b""
            res = b"\n".join([line for line in lines if not line.startswith(b"=== ") and not line.startswith(b">>> ") and not line.startswith(b"paste mode; Ctrl-C to cancel, Ctrl-D to finish")])
        if res.endswith(b"\n>>> "):
            res = res[:-5]
        return res.decode("utf-8")

    def kill(self):
        try:
            self.ser.write(b"\r\x03")
            self.ser.close()
            time.sleep(0.1)
        except:
            pass

class F469Kernel(Kernel):
    implementation = 'F469'
    implementation_version = '1.0'
    language = 'python'
    language_version = '3.6'
    language_info = {
        'name': 'python',
        'mimetype': 'text/plain',
        'extension': '.py',
    }
    banner = "F469 kernel - as useful as a parrot"
    
    mpy = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        if not silent:
            lines = code.split("\n")
            connect_lines = [line for line in lines if line.startswith("%spawn ") or line.startswith("%connect ")]
            if self.mpy == None and len(connect_lines) == 0:
                stream_content = {'name': 'stderr', 'text': "Not connected to micropython\nUse `%spawn <path/to/micropython>` or `%connect <port> <baudrate=115200>`"}
                self.send_response(self.iopub_socket, 'stream', stream_content)
                return {'status': 'error',
                    # The base class increments the execution count
                    'execution_count': self.execution_count,
                    'payload': [],
                    'user_expressions': {},
                }
            if len(connect_lines) > 0:
                if self.mpy is not None:
                    self.mpy.kill()
                    time.sleep(0.1)
                cmd = connect_lines[-1]
                try:
                    if "%spawn" in cmd:
                        cmd = cmd.replace("%spawn ","").strip()
                        self.mpy = MPYBinary(cmd)
                    if "%connect" in cmd:
                        cmd = cmd.replace("%connect ","").strip()
                        arr = [e for e in cmd.split(" ") if len(e) > 0]
                        self.mpy = MPYSerial(*arr)
                except Exception as e:
                    self.mpy = None
                    stream_content = {'name': 'stderr', 'text': "Can't connected to micropython: %r" % e}
                    self.send_response(self.iopub_socket, 'stream', stream_content)
                    return {'status': 'error',
                        # The base class increments the execution count
                        'execution_count': self.execution_count,
                        'payload': [],
                        'user_expressions': {},
                    }
                code = "\n".join([line for line in lines if line not in connect_lines])
            code = code.strip()+"\r\n"
            try:
                res = self.mpy.exec(code)
            except Exception as e:
                stream_content = {'name': 'stderr', 'text': "Kernel panic! %r" % e}
                self.send_response(self.iopub_socket, 'stream', stream_content)
                return {'status': 'error',
                    # The base class increments the execution count
                    'execution_count': self.execution_count,
                    'payload': [],
                    'user_expressions': {},
                }


            stream_content = {'name': 'stdout', 'data': res}
            self.send_response(self.iopub_socket, 'stream', stream_content)

            content = {
                'source': 'kernel',
                'data': {
                    'text/plain': res
                },

            }
            self.send_response(self.iopub_socket,
                'display_data', content)

        return {'status': 'ok',
                # The base class increments the execution count
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
               }
    def do_shutdown(self, restart):
        # self.mpy.kill(9)
        pass

if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=F469Kernel)