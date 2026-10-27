"""Run every smoke test in order and print a summary. Exit code 0 only if all pass."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
TESTS = sorted(HERE.glob("test_*.py"))
LABEL = {0: "PASS", 1: "FAIL", 2: "SKIP (missing key)"}

results = []
for test in TESTS:
    code = subprocess.call([sys.executable, str(test), *sys.argv[1:]], cwd=HERE)
    results.append((test.stem, code))

print("\n=== summary ===")
for name, code in results:
    print(f"{LABEL.get(code, f'exit {code}'):<20} {name}")
sys.exit(0 if all(code == 0 for _, code in results) else 1)
