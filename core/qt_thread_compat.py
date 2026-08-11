from PyQt5.QtCore import QThread
import types
import inspect
class QtThreadCompat(QThread):
    """\nA QThread that mimics the API of threading.Thread just enough for\nexisting GUI code (.join, .is_alive, .daemon) to keep working.\n"""
    def __init__(self, target, args=(), kwargs=None, parent=None):
        super().__init__(parent)
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.daemon = True
    def run(self):
        self._target(*self._args, **self._kwargs)
    def join(self, timeout=None):
        msec = (-1) if timeout is None else int(timeout * 1000)
        self.wait(msec)
    def is_alive(self):
        return self.isRunning()