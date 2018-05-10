import mock
import tornado
import pytest
import socket
from circus.sockets import CircusSocket, CircusSockets


@pytest.fixture
def available_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("", 0))
        return s.getsockname()[1]
    finally:
        s.close()


@pytest.fixture
def file_path(tmpdir):
    filename = tmpdir.ensure('socket')
    filename.remove()
    return filename.strpath


@pytest.fixture
def tcp_socket():
    sock = CircusSocket('somename', 'localhost', 0)
    yield sock
    sock.close()


@pytest.fixture
def socket_manager():
    mgr = CircusSockets()
    for i in range(5):
        mgr.add(str(i), 'localhost', 0)
    yield mgr
    mgr.close_all()


@pytest.fixture
def MagicMockFuture():
    class MagicMockFuture(mock.MagicMock, tornado.concurrent.Future):
        def cancel(self):
            return False

        def cancelled(self):
            return False

        def running(self):
            return False

        def done(self):
            return True

        def result(self, timeout=None):
            return None

        def exception(self, timeout=None):
            return None

        def add_done_callback(self, fn):
            fn(self)

        def set_result(self, result):
            pass

        def set_exception(self, exception):
            pass

        def __del__(self):
            # Don't try to print non-consumed exceptions
            pass

    return MagicMockFuture


@pytest.fixture
def FakeProcess():
    class FakeProcess(object):
        def __init__(self, pid, status, started=1, age=1):
            self.status = status
            self.pid = pid
            self.started = started
            self.age = age
            self.stopping = False
            self.children = lambda *a, **kw: []
            self.returncode = lambda: 0

        def is_alive(self):
            return True

        def stop(self):
            pass

    return FakeProcess


@pytest.fixture
def arbiter(tmpdir, file_path, io_loop):
    wdir = tmpdir.strpath
    args = ['circus/tests/generic.py', callable_path, testfile]
    worker = {'cmd': PYTHON, 'args': args, 'working_dir': wdir, 'name': 'test', 'graceful_timeout': 2}
    worker.update(kw)
    if not arbiter_kw:
        arbiter_kw = {}
    debug = arbiter_kw['debug'] = kw.get('debug', arbiter_kw.get('debug', False))
    # -1 => no periodic callback to manage_watchers by default
    arbiter_kw['check_delay'] = kw.get('check_delay', arbiter_kw.get('check_delay', -1))

    arbiter_kw['controller'] = "tcp://127.0.0.1:%d" % 0
    arbiter_kw['pubsub_endpoint'] = "tcp://127.0.0.1:%d" % 0
    arbiter_kw['multicast_endpoint'] = "udp://237.219.251.97:12027"

    if stats:
        arbiter_kw['statsd'] = True
        arbiter_kw['stats_endpoint'] = "tcp://127.0.0.1:%d" % 0
        arbiter_kw['statsd_close_outputs'] = not debug

    if async:
        arbiter_kw['background'] = False
        arbiter_kw['loop'] = io_loop
    else:
        arbiter_kw['background'] = True

    arbiter = cls.arbiter_factory([worker], plugins=plugins, **arbiter_kw)
    return arbiter
