import os
import signal

_KINDER = []


def remove_child(pid: int):
    _KINDER.remove(pid)


def add_child(pid: int):
    _KINDER.append(pid)


def toeten_die_kinder():
    for pid in _KINDER:
        print(f"Sending SIGTERM to {pid}")
        os.killpg(os.getpgid(pid), signal.SIGTERM)
