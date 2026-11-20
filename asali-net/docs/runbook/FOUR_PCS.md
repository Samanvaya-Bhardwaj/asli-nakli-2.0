# Running Asali on four computers

This is the checklist for the day the four computers run together. Nothing here has been run on four computers yet.
The stack generator and the checks are tested as data and on one computer; the Docker parts need Docker, which this
project's development PC does not have.

| Computer | Role | Runs |
|---|---|---|
| PC-A (16 GB Windows) | People | directory, regulator, consumer-delhi, consumer-mumbai |
| PC-B (16 GB Mac) | Pharma | tarang, medivra, kesar |
| PC-C (8 GB Windows) | Distributors | dist-north, dist-west, dist-south |
| PC-D (8 GB Windows) | Shops | shop-delhi, shop-mumbai, shop-bengaluru |

Do the steps in order. After each one, the "You should see" line says what success looks like.

## 1. Put the computers on one network

All four join one Wi-Fi network that lets devices talk to each other: a phone hotspot or a home router. Campus Wi-Fi often
blocks this ("client isolation").

On each computer, find its address: Windows `ipconfig`, Mac `ipconfig getifaddr en0`. Then on PC-B, PC-C and PC-D start the listener:

```powershell
python infra/scripts/check_lan.py --listen
```

On PC-A, from the repository folder `asali-net/`:

```powershell
python infra/scripts/check_lan.py --peers <PC-B ip> <PC-C ip> <PC-D ip>
```

**You should see** `ok` in every cell. **If a cell says BLOCKED:** the Wi-Fi blocks device-to-device traffic, or a firewall is in the way
(step 4). If the Wi-Fi is the problem, install Tailscale on all four computers, use their `100.x` addresses, and run the check again.

## 2. Time

Turn on automatic time. Windows: Settings, Time and language, Sync now. Mac: on by default. Requests between organisations are
rejected when the clocks differ by more than 2 minutes, and the error names the difference.

## 3. Docker

- **Windows (PC-A, PC-C, PC-D):** in an administrator PowerShell run `wsl --install --no-distribution`, restart, then install Docker Desktop.
  Create `%UserProfile%\.wslconfig` with `[wsl2]` and `memory=4GB` on the 8 GB computers, `memory=8GB` on PC-A.
- **Mac (PC-B):** install Docker Desktop for Apple silicon.

**You should see** `docker version` print a client and a server.
**If Docker will not install** (no administrator rights): tell the team. That computer's organisations then run in one other computer's
simulation stack, and the evidence must say so. Do not call it a four-computer run.

## 4. Firewall

- **Windows:** set the Wi-Fi network to Private (Settings, Network and internet, Wi-Fi, the network, Network profile type), then in an
  administrator PowerShell: `infra\scripts\windows_firewall.ps1`.
- **Mac:** System Settings, Network, Firewall: allow Docker.

**You should see** the same check from step 1, run again from another computer, still say `ok`.

## 5. Certificates

Phones need HTTPS to use the camera. One person runs `mkcert -install` on their computer. Copy `rootCA.pem` and `rootCA-key.pem`
(from `mkcert -CAROOT`) to the other three computers' `mkcert -CAROOT` folder. **Never commit these two files.** Then on every computer:

```powershell
mkcert -install
python infra/scripts/make_cert.py --pc PC-C --ip <this computer's ip>
```

Use the right `--pc` name for each computer. **You should see** `certificate for ... written to infra/out/<PC>/certs`.
**On a phone used for scanning:** install `rootCA.pem`. Android: Settings, Security, Install certificate, CA certificate. iPhone: install
the profile, then Settings, General, About, Certificate Trust Settings, switch it on.

## 6. Start the stacks

PC-A first, because everyone registers with the directory. On PC-A:

```powershell
python infra/scripts/make_stack.py --pc PC-A --ip <PC-A ip>
docker compose -f infra/out/PC-A/compose.yml --env-file infra/out/PC-A/.env up -d --build
```

Copy the generated `JOIN_TOKEN` and `ADMIN_TOKEN` lines from `infra/out/PC-A/.env` into the `.env` of the other three computers (create the
file by running `make_stack.py` there once, then replace those two lines). On PC-B, PC-C and PC-D:

```powershell
python infra/scripts/make_stack.py --pc PC-C --ip <this computer's ip> --directory-url https://<PC-A ip>:8400
docker compose -f infra/out/PC-C/compose.yml --env-file infra/out/PC-C/.env up -d --build
```

**You should see** this on each computer after about a minute:

```powershell
python infra/scripts/check_stack.py --pc PC-C --ip <this computer's ip> --cafile infra/out/PC-C/certs/rootCA.pem
```

one line `OK <organisation> <computer>` per organisation, then `directory lists 12 organisations, 12 online` once all four are up.
**If an organisation says FAIL:** `docker compose -f infra/out/<PC>/compose.yml logs <organisation>-app`. The most common causes are a wrong
`JOIN_TOKEN` (registration refused) and the clocks (step 2).

## 7. Put data in

From PC-A (it holds the directory), with the staff password from `infra/out/PC-A/secrets.json` (or set `ASALI_STAFF_PASSWORD`):

```powershell
$dir = "https://<PC-A ip>:8400"; $ca = "infra/out/PC-A/certs/rootCA.pem"
python seed/seed_network.py --directory-url $dir --ca $ca --password <staff password>
python seed/scenarios.py --directory-url $dir --ca $ca --password <staff password>
python ml/post_corpus.py --directory-url $dir --ca $ca --password <staff password>
python seed/scenarios.py --directory-url $dir --ca $ca --password <staff password> --text
```

The scripts read each organisation's address from the directory, so every computer in section 6 must be running and listed first.
They keep their progress in `infra/out/SIM/` on the computer you run them from, so run all four from the same place.
This addressing has been tested against the local directory only; it has not yet been run across four computers.

## 8. Prove it is spread over four computers

```powershell
python infra/scripts/collect_evidence.py --directory-url https://<PC-A ip>:8400 --consumer-url https://<PC-A ip>:8402 --cafile infra/out/PC-A/certs/rootCA.pem --scenarios <path to scenarios.json>
```

**You should see** `Multi-machine run proven.` and a folder under `docs/evidence/four_pcs/`. If the script says "Not proven", the run is not
evidence of distribution: write why in `docs/evidence/four_pcs/NOT_RUN.md` and say so in the report.

## Turning things off

`docker compose -f infra/out/<PC>/compose.yml down` stops a stack. To show the "cannot check" answer, stop one organisation:
`docker compose -f infra/out/PC-C/compose.yml stop dist-west-app`, check a pack that went through it, then `start` it again.
