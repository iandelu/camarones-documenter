"""A small interactive program for the terminal tests: says it is ready and its size, echoes lines, answers `size`,
prints `bytes N` x's or a line with accents, exits 3 on `exit`. On a resize it says its new size (SIGWINCH, POSIX)."""
import os, signal, sys


def size():
    s = os.get_terminal_size(sys.stdout.fileno())
    return f"{s.columns}x{s.lines}"


if hasattr(signal, "SIGWINCH"):
    signal.signal(signal.SIGWINCH, lambda *_: print(f"winch {size()}", flush=True))
print(f"ready {size()}", flush=True)
for line in sys.stdin:
    word = line.strip()
    if word == "exit":
        sys.exit(3)
    if word == "size":
        print(f"size {size()}", flush=True)
    elif word.startswith("bytes "):
        print("x" * int(word[6:]), flush=True)
    elif word == "accents":
        print("año ─ fin", flush=True)
    else:
        print(f"echo {word} ({len(word)})", flush=True)
