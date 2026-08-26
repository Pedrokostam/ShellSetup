from __future__ import annotations
from dataclasses import dataclass, field
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, Any

CARRIAGE_RETURN = b"\r"
NEWLINE = b"\n"
BACKSPACE = b"\b"

CARRIAGE_RETURN_NUM = CARRIAGE_RETURN[0]
NEWLINE_NUM = NEWLINE[0]
BACKSPACE_NUM = BACKSPACE[0]


@dataclass
class SinkStat:
    last_check_length: int
    last_check_time: float
    last_check_result: bool
    interval: float

    @classmethod
    def new(cls) -> SinkStat:
        interval = 1.0
        return SinkStat(
            last_check_length=0,
            interval=interval,
            last_check_result=False,
            last_check_time=time.perf_counter() - interval,
        )

    def update(self, new_length: int) -> bool:
        is_diff = self.last_check_length != new_length
        if is_diff or time.perf_counter() - self.last_check_time >= self.interval:
            self.last_check_result = is_diff
            self.last_check_length = new_length
            self.last_check_time = time.perf_counter()
        return self.last_check_result


class StreamSink:
    ENCODING = "utf-8"
    REGGY = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")

    def __init__(self, indicators: list[str] | None = None):
        self.captured_out = bytearray()
        self.captured_err = bytearray()
        self._window = bytearray()
        self._thread_out: threading.Thread | None = None
        self._thread_err: threading.Thread | None = None
        self.indicators = indicators or [
            "[=-   ]",
            "[-=-  ]",
            "[ -=- ]",
            "[  -=-]",
            "[   -=]",
            "[  -=-]",
            "[ -=- ]",
            "[-=-  ]",
        ]
        self._indicator_index = 0
        self.stats: SinkStat = SinkStat.new()

    def _intercept(self, stream: IO[bytes], target: bytearray):
        while True:
            chunk_out = stream.read(8)
            target.extend(chunk_out)

    def is_started(self) -> bool:
        return (bool(self._thread_out) and self._thread_out.is_alive()) or (
            bool(self._thread_err) and self._thread_err.is_alive()
        )

    def get_length(self) -> int:
        return len(self.captured_out)

    def start_capture(self, pop: subprocess.Popen[bytes]):
        if self._thread_out and self._thread_out.is_alive():
            return
        # assert isinstance(stream, TextIOBase)
        self._thread_out = threading.Thread(
            target=self._intercept,
            kwargs={"stream": pop.stdout, "target": self.captured_out},
            daemon=True,
        )
        self._thread_err = threading.Thread(
            target=self._intercept,
            kwargs={"stream": pop.stderr, "target": self.captured_err},
            daemon=True,
        )
        self._thread_out.start()
        self._thread_err.start()

    def wait(self):
        if self._thread_out and self._thread_out.is_alive():
            self._thread_out.join()
        if self._thread_err and self._thread_err.is_alive():
            self._thread_err.join()

    def dump_output_bytes(self) -> bytes:
        return bytes(self.captured_out)

    def dump_output(self) -> str:
        return self.captured_out.decode(encoding=StreamSink.ENCODING)

    def dump_error_bytes(self) -> bytes:
        return bytes(self.captured_err)

    def dump_error(self) -> str:
        return self.captured_err.decode(encoding=StreamSink.ENCODING)

    def is_finished(self) -> bool:
        return (
            bool(self._thread_out)
            and not self._thread_out.is_alive()
            and bool(self._thread_err)
            and not self._thread_err.is_alive()
        )

    def indicator(self) -> str:
        new_len = len(self.captured_out) + len(self.captured_err)
        if self.stats.update(new_len):
            self._indicator_index = (self._indicator_index + 1) % len(self.indicators)
        return self.indicators[self._indicator_index]


if __name__ == "__main__":
    a = ["python3", "install_apps.py", "--debug", "install", "--groups", "test"]
    if len(sys.argv) > 1 and "p" in sys.argv[1]:
        a += ["--progress"]
    pop = subprocess.Popen(
        a,
        universal_newlines=False,
        shell=False,
        text=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert pop.stdout
    sink = StreamSink()
    sink.start_capture(pop)
    while not sink.is_finished():
        time.sleep(0.25)
        w = sink.indicator()
        print(f"\r{w}", end="")

    print(sink.dump_output())
    sys.exit(0)
