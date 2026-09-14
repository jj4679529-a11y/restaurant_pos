"""Run blocking HTTP/startup work off the Qt GUI thread."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class JobSignals(QObject):
    done = Signal(object, object)


class Job(QRunnable):
    def __init__(self, operation, completed):
        super().__init__()
        self.operation = operation
        self.signals = JobSignals()
        self.signals.done.connect(completed)

    def run(self):
        try:
            result = self.operation()
        except Exception as error:
            self.signals.done.emit(None, error)
        else:
            self.signals.done.emit(result, None)


def submit(operation, completed):
    job = Job(operation, completed)
    QThreadPool.globalInstance().start(job)
    return job
