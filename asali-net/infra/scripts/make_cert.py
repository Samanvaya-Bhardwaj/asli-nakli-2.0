"""Make this PC's certificate with mkcert, for its IP address, its host name and localhost (PLAN.md 16.4 step 5).

    python infra/scripts/make_cert.py --pc PC-C --ip 192.168.1.23

Needs mkcert on the PATH, and `mkcert -install` run once on every PC with the SAME root CA (copy rootCA.pem and
rootCA-key.pem from the first PC into `mkcert -CAROOT` on the others; never commit them). Writes
infra/out/<PC>/certs/{cert.pem,key.pem,rootCA.pem}.
"""

import argparse
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--ip", required=True)
    args = ap.parse_args()
    if shutil.which("mkcert") is None:
        print(
            "mkcert is not installed. Install it first (see docs/runbook/FOUR_PCS.md, step 5).",
            file=sys.stderr,
        )
        return 2
    out = ROOT / "infra" / "out" / args.pc / "certs"
    out.mkdir(parents=True, exist_ok=True)
    names = [args.ip, socket.gethostname(), "localhost", "127.0.0.1"]
    subprocess.run(
        ["mkcert", "-cert-file", str(out / "cert.pem"), "-key-file", str(out / "key.pem"), *names], check=True
    )
    caroot = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True, check=True).stdout.strip()
    shutil.copy(Path(caroot) / "rootCA.pem", out / "rootCA.pem")
    print(f"certificate for {', '.join(names)} written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
