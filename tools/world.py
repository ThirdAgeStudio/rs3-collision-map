import argparse
import multiprocessing
import time
from pathlib import Path

import build
import encode

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data"
PROGRESS_EVERY = 500

worker_dump = None


def start_worker(dump_folder):
    global worker_dump
    worker_dump = build.MapDump(dump_folder)


def encode_square(square):
    square_x, square_z = square
    walls = worker_dump.collision(square_x, square_z)
    corners = build.square_corners(worker_dump, square_x, square_z)
    return square, encode.square_strings(square_x, square_z, walls, corners)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Build Collision Map's data files from an rs3cache dump.")
    parser.add_argument("dump", type=Path, help="rs3cache's output folder (with tiles/, locations/ and location_configs.json)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="where the data files go (default: data/)")
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    squares = build.square_names(arguments.dump)
    started = time.time()
    encoded = {}
    with multiprocessing.Pool(arguments.workers, initializer=start_worker, initargs=(arguments.dump,)) as pool:
        for count, (square, strings) in enumerate(pool.imap(encode_square, squares, chunksize=16), 1):
            if strings is not None:
                encoded[square] = strings
            if count % PROGRESS_EVERY == 0:
                print(f"{count}/{len(squares)} squares, {time.time() - started:.0f} s", flush=True)

    arguments.output.mkdir(parents=True, exist_ok=True)
    for old_file in arguments.output.glob("*.lua"):
        old_file.unlink()
    files = encode.group_files(encoded)
    for name, text in files.items():
        (arguments.output / name).write_text(text)
    total_bytes = sum(len(text) for text in files.values())
    print(f"{len(squares)} squares, {len(encoded)} with collision: {len(files)} files, "
          f"{total_bytes / 1e6:.2f} MB, {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
