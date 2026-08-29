from __future__ import annotations
import time
import signal
import subprocess
from collections.abc import Sequence
from typing import Any, Literal, TypeAlias, overload

from python.cmd_parts import CmdParts
from python.context.child_processes import add_child, remove_child
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


def _monitor(
    pop: subprocess.Popen[Any], timeout: float, start_time: float, sink: StreamSink
):
    try:
        ret_code = pop.poll()
        if ret_code is not None:
            return ret_code
        if time.perf_counter() - start_time > timeout:
            raise subprocess.TimeoutExpired(pop.args, timeout=timeout)
        time.sleep(0.25)
    except KeyboardInterrupt:
        sink.enter_prompt_mode()
        prompt_start = time.perf_counter()
        while not sink.can_prompt:
            time.sleep(0.25)
            if time.perf_counter() - prompt_start > 10:
                pass
                # raise KeyboardInterrupt()
        inputted = input(
            "\nPress S to skip this command, Ctrl-C to abort the whole script"
            + " " * 30
        )
        print(f"Input is '{inputted}'")
        if inputted.casefold() == "s":
            print("killym")
            pop.kill()
            ret_code = pop.returncode
            print(f"retocodo: {ret_code}")
            sink.exit_prompt_mode()
            return ret_code
        sink.exit_prompt_mode()
        print("returning")
    return None


def _run(
    cmd: _CMD,
    shell: bool,
    timeout: float = TIMEOUT,
    prepend_sudo: bool = False,
    check: bool = False,
    **kwargs,
):
    sink = kwargs.get("sink")
    if not isinstance(sink, StreamSink):
        sink = StreamSink()
    _cmd = _convert_cmd(cmd, shell=True, prepend_sudo=prepend_sudo)
    pop = subprocess.Popen(
        _cmd,
        universal_newlines=False,
        shell=shell,
        text=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    add_child(pop.pid)
    sink.start_capture(pop)
    start_time = time.perf_counter()
    ret_code = None
    while True:
        ret_code = _monitor(pop, timeout, start_time, sink)
        print(" " * 60 + "rec_code->" + str(ret_code), end="")
        if ret_code is not None:
            break
    remove_child(pop.pid)
    if check and ret_code != 0:
        raise subprocess.CalledProcessError(
            ret_code, pop.args, sink.dump_output(), sink.dump_error()
        )
    res = subprocess.CompletedProcess(
        args=_cmd,
        returncode=ret_code,
        stdout=sink.dump_output(),
        stderr=sink.dump_error(),
    )
    print(" " * 60 + "ret_code->" + str(ret_code), end="")
    return res


def run(
    cmd: _CMD,
    prepend_sudo: bool = False,
    check: bool = False,
    timeout: float = TIMEOUT,
    **kwargs,
) -> subprocess.CompletedProcess[str]:
    return _run(
        cmd,
        prepend_sudo=prepend_sudo,
        timeout=timeout,
        check=check,
        shell=True,
        **kwargs,
    )


def run_shell(
    cmd: _CMD,
    prepend_sudo: bool = False,
    check: bool = False,
    timeout: float = TIMEOUT,
    **kwargs,
) -> subprocess.CompletedProcess[str]:
    return _run(
        cmd,
        prepend_sudo=prepend_sudo,
        timeout=timeout,
        check=check,
        shell=True,
        **kwargs,
    )
