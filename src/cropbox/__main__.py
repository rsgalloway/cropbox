import argparse


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cropbox")
    parser.add_argument("media", nargs="?", help="Optional media path to open on launch")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    from cropbox.app import main as run_app

    return run_app(initial_media=args.media)


if __name__ == "__main__":
    raise SystemExit(main())
