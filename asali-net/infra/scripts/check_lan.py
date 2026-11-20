"""Can these computers reach each other? A matrix of TCP connects to the ports the stacks will use.

    python infra/scripts/check_lan.py --peers 192.168.1.11 192.168.1.23 192.168.1.30
    python infra/scripts/check_lan.py --listen            # on a peer, before its stack is up

Run it before anything else (PLAN.md 16.4 step 1). Campus Wi-Fi often blocks device-to-device traffic.
"""

import argparse
import socket
import sys
import threading

import network_model

PROBE_PORTS = [8400, 8101, 8201, 8301]  # one from each group is enough to prove the path


def reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def listen(ports: list[int]) -> None:
    servers = []
    for p in ports:
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", p))
        s.listen()
        threading.Thread(
            target=lambda srv=s: [srv.accept()[0].close() for _ in iter(int, 1)], daemon=True
        ).start()
        servers.append(s)
    print(f"listening on {ports}; press Ctrl+C to stop")
    threading.Event().wait()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peers", nargs="*", default=[])
    ap.add_argument("--listen", action="store_true")
    args = ap.parse_args()
    net = network_model.load()
    ports = sorted({net.directory.port, *(o.port for o in net.orgs.values())})
    if args.listen:
        listen([p for p in ports if p in PROBE_PORTS])
        return 0
    if not args.peers:
        print("give --peers <ip> ... or --listen", file=sys.stderr)
        return 2
    print("peer".ljust(18) + "".join(str(p).rjust(7) for p in PROBE_PORTS))
    bad = 0
    for peer in args.peers:
        row = [reachable(peer, p) for p in PROBE_PORTS]
        bad += row.count(False)
        print(peer.ljust(18) + "".join(("ok" if ok else "BLOCKED").rjust(7) for ok in row))
    if bad:
        print(
            "\nSome ports are blocked. Check the firewall (windows_firewall.ps1), the Wi-Fi network profile, and client isolation."
        )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
