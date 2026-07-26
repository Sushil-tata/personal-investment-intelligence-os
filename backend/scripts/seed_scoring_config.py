from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "config" / "scoring"
DST = ROOT / "data" / "mock" / "scoring"


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for item in SRC.glob("*.yaml"):
        shutil.copy(item, DST / item.name)


if __name__ == "__main__":
    main()
