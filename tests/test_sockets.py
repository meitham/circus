import fcntl
import os
import socket

import mock

import pytest
from circus.sockets import CircusSocket, CircusSockets
from circus.tests.support import IS_WINDOWS

try:
    import IN
except ImportError:
    pass


def so_bindtodevice_supported():
    try:
        if hasattr(IN, 'SO_BINDTODEVICE'):
            return True
    except NameError:
        pass
    return False


def is_nonblock(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    nonblock = fl & os.O_NONBLOCK
    return nonblock != 0


@pytest.mark.skipif(
    IS_WINDOWS, reason="Unix sockets not supported on this platform")
def test_load_from_config_replace(tmpdir):
    sockfile = tmpdir.ensure('path').strpath

    config = {'name': 'somename', 'path': sockfile, 'replace': False}
    sock = CircusSocket.load_from_config(config)
    try:
        with pytest.raises(OSError):
            sock.bind_and_listen()
    finally:
        sock.close()

    config = {'name': 'somename', 'path': sockfile, 'replace': True}
    sock = CircusSocket.load_from_config(config)
    sock.bind_and_listen()
    try:
        assert sock.replace == True
    finally:
        sock.close()


@pytest.mark.skipif(
    IS_WINDOWS, reason="Unix sockets not supported on this platform")
def test_load_from_config_blocking():
    # test default to false
    config = {'name': 'somename', 'host': 'localhost', 'port': 0}
    sock = CircusSocket.load_from_config(config)
    assert sock.blocking == False
    sock.bind_and_listen()
    assert is_nonblock(sock.fileno())
    sock.close()

    # test when true
    config = {
        'name': 'somename',
        'host': 'localhost',
        'port': 0,
        'blocking': True
    }
    sock = CircusSocket.load_from_config(config)
    assert sock.blocking == True
    sock.bind_and_listen()
    assert not is_nonblock(sock.fileno())
    sock.close()


@pytest.mark.skipif(
    IS_WINDOWS, reason="Unix sockets not supported on this platform")
def test_unix_socket(file_path):
    sockfile = file_path
    sock = CircusSocket('somename', path=sockfile, umask=0)
    try:
        sock.bind_and_listen()
        assert os.path.exists(sockfile)
        permissions = oct(os.stat(sockfile).st_mode)[-3:]
        assert permissions == '777'
    finally:
        sock.close()


@pytest.mark.skipif(
    IS_WINDOWS, reason="Unix sockets not supported on this platform")
def test_unix_cleanup(file_path):
    sockets = CircusSockets()
    sockfile = file_path
    try:
        sockets.add('unix', path=sockfile)
        sockets.bind_and_listen_all()
        assert os.path.exists(sockfile)
    finally:
        sockets.close_all()
        assert not os.path.exists(sockfile)


@pytest.mark.skip(not so_bindtodevice_supported(),
                  'SO_BINDTODEVICE unsupported')
def test_bind_to_interface():
    config = {'name': '', 'host': 'localhost', 'port': 0, 'interface': 'lo'}

    sock = CircusSocket.load_from_config(config)
    assert sock.interface == config['interface']
    sock.setsockopt = mock.Mock()
    try:
        sock.bind_and_listen()
        sock.setsockopt.assert_any_call(socket.SOL_SOCKET, IN.SO_BINDTODEVICE,
                                        config['interface'] + '\0')
    finally:
        sock.close()


def test_inet6():
    config = {'name': '', 'host': '::1', 'port': 0, 'family': 'AF_INET6'}
    sock = CircusSocket.load_from_config(config)
    assert sock.host == config['host']
    assert sock.port == config['port']
    sock.setsockopt = mock.Mock()
    try:
        sock.bind_and_listen()
        # we should have got a port set
        assert sock.port != 0
    finally:
        sock.close()


@pytest.mark.skipif(
    not hasattr(socket, 'SO_REUSEPORT'),
    reason='socket.SO_REUSEPORT unsupported')
def test_reuseport_supported():
    config = {'name': '', 'host': 'localhost', 'port': 0, 'so_reuseport': True}

    sock = CircusSocket.load_from_config(config)
    try:
        sockopt = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT)
    except socket.error:
        # see #699
        return
    finally:
        sock.close()

    assert sock.so_reuseport
    assert sockopt != 0


def test_reuseport_unsupported():
    config = {'name': '', 'host': 'localhost', 'port': 0, 'so_reuseport': True}
    saved = None

    try:
        if hasattr(socket, 'SO_REUSEPORT'):
            saved = socket.SO_REUSEPORT
            del socket.SO_REUSEPORT
        sock = CircusSocket.load_from_config(config)
        assert sock.so_reuseport == False
    finally:
        if saved is not None:
            socket.SO_REUSEPORT = saved
        sock.close()


@pytest.mark.skipif(
    not hasattr(os, 'set_inheritable'),
    reason='os.set_inheritable unsupported')
@pytest.mark.skipif(
    IS_WINDOWS, reason="Unix sockets not supported on this platform")
def test_set_inheritable(file_path):
    sock = CircusSocket('somename', path=file_path, umask=0)
    try:
        sock.bind_and_listen()
        assert sock.get_inheritable()
    finally:
        sock.close()


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


def test_socket(tcp_socket):
    tcp_socket.bind_and_listen()


def test_manager(socket_manager):
    port = socket_manager['1'].port
    socket_manager.bind_and_listen_all()
    # we should have a port now
    assert port != socket_manager['1'].port


def test_load_from_config_no_proto():
    """When no proto in the config, the default (0) is used."""
    config = {'name': ''}
    sock = CircusSocket.load_from_config(config)
    assert sock.proto == 0
    sock.close()


def test_load_from_config_unknown_proto():
    """Unknown proto in the config raises an error."""
    config = {'name': '', 'proto': 'foo'}
    with pytest.raises(socket.error):
        CircusSocket.load_from_config(config)


@pytest.mark.skipif(
    IS_WINDOWS, reason="Unix sockets not supported on this platform")
def test_load_from_config_umask(file_path):
    sockfile = file_path
    config = {'name': 'somename', 'path': sockfile, 'umask': 0}
    sock = CircusSocket.load_from_config(config)
    try:
        assert sock.umask == 0
    finally:
        sock.close()
