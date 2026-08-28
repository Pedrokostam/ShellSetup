from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Literal, TypeAlias, overload

from python.cmd_parts import CmdParts
from python.error import AppInstallError
from python.stream_sink import StreamSink

_CMD: TypeAlias = str | CmdParts | Sequence[str]

TIMEOUT = 20 * 60


@overload
def _convert_cmd(
    cmd: _CMD,
    shell: Literal[False],
    prepend_sudo: bool = False,
) -> list[str]: ...


@overload
def _convert_cmd(
    cmd: _CMD,
    shell: Literal[True],
    prepend_sudo: bool = False,
) -> str: ...


def _convert_cmd(
    cmd: _CMD, shell: bool = False, prepend_sudo: bool = False
) -> str | list[str]:
    from python.context.system import is_windows

    if not isinstance(cmd, CmdParts):
        cmd = CmdParts(cmd)
    if prepend_sudo:
        if is_windows():
            raise AppInstallError(
                problem="Cannot elevate a Windows installer. Rerun the script with elevation.",
            )
        else:
            cmd.prepend(["sudo", "-n"])
    if shell:
        return cmd.to_single_string()
    return cmd.to_list()


def run_interactive(
    cmd: _CMD,
    shell: bool = False,
    prepend_sudo: bool = False,
    check: bool = False,
    timeout: float = TIMEOUT,
):
    """
    Starts a process where outputs and inputs are piped to the active terminal.
    Nothing is captured
    """
    return subprocess.run(
        _convert_cmd(cmd, shell=shell, prepend_sudo=prepend_sudo),
        shell=shell,
        capture_output=False,
        check=check,
        timeout=timeout,
    )


def run(
    cmd: _CMD,
    prepend_sudo: bool = False,
    check: bool = False,
    timeout: float = TIMEOUT,
    **kwargs,
):
    if (sink := kwargs.get("sink")) and isinstance(sink, StreamSink):
        _cmd = _convert_cmd(cmd, shell=False, prepend_sudo=prepend_sudo)
        pop = subprocess.Popen(
            _cmd,
            universal_newlines=False,
            shell=False,
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        sink.start_capture(pop)
        ret_code = pop.wait(timeout=timeout)
        res = subprocess.CompletedProcess(
            args=_cmd,
            returncode=ret_code,
            stdout=sink.dump_output(),
            stderr=sink.dump_error(),
        )
        return res
    return subprocess.run(
        _convert_cmd(cmd, shell=False, prepend_sudo=prepend_sudo),
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def run_shell(
    cmd: _CMD,
    prepend_sudo: bool = False,
    check: bool = False,
    timeout: float = TIMEOUT,
    **kwargs,
):
    if (sink := kwargs.get("sink")) and isinstance(sink, StreamSink):
        _cmd = _convert_cmd(cmd, shell=True, prepend_sudo=prepend_sudo)
        pop = subprocess.Popen(
            _cmd,
            universal_newlines=False,
            shell=True,
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        sink.start_capture(pop)
        ret_code = pop.wait(timeout=timeout)
        res = subprocess.CompletedProcess(
            args=_cmd,
            returncode=ret_code,
            stdout=sink.dump_output(),
            stderr=sink.dump_error(),
        )
        return res
    return subprocess.run(
        _convert_cmd(cmd, shell=True, prepend_sudo=prepend_sudo),
        shell=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )
