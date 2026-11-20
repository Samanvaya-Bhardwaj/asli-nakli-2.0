# Starting the four-computer run

One file per computer does everything: starts Docker and the databases, sets up Python, builds the portal, loads the
demo data the first time, and starts that computer's organisations.

| Computer | Runs | Start it with |
|---|---|---|
| PC-A (Windows) | directory, regulator, two consumer portals | double-click `start-PC-A.cmd` |
| PC-B (Mac) | Tarang, Medivra, Kesar (pharma) | double-click `start-PC-B.command` |
| PC-C (Windows) | three distributors | double-click `start-PC-C.cmd` |
| PC-D (Windows) | three shops | double-click `start-PC-D.cmd` |

**Start PC-A first.** It holds the directory that the other three register with. The others wait for it.

Leave each window open during the demo. Closing it, or pressing Ctrl+C, stops that computer's organisations.
Running the file again restarts them and keeps their data.

## Once per computer, before the first start

1. **Docker Desktop** installed and started once. On Windows, allow WSL 2 when it asks.
2. **The project**: `git clone https://github.com/Samanvaya-Bhardwaj/asli-nakli-2.0.git`, then work in its `asali-net`
   folder. The clone already has everything the start file needs:
   - `infra/four_pcs.yaml`: each computer's address and the team phrase. If an address changes, edit it on all four.
   - `infra/out/bundles/<PC>.zip`: each computer's demo data.
   - `apps/portal-web/dist`: the built portal, so Node.js is not required. With Node.js installed, the start file
     rebuilds the portal when its source is newer.

Python does not need to be set up by hand. The start file creates the Python 3.11 environment the first time, which takes
a few minutes.

## The first start on each computer

- **Windows** asks whether Python may use the network. Tick **Private and Public**, then click Allow.
- **macOS** asks whether Python may accept incoming connections. Click Allow.
- If double-clicking `start-PC-B.command` does nothing, open Terminal in the folder and run `bash start-PC-B.command`.

## Success looks like this

```
PC-C (…, 192.168.39.77) is up. Organisations here:
  North Star Distributors      http://192.168.39.77:8101
  ...
The directory at http://192.168.52.152:8400 lists 12 organisations, 12 online.
Staff login on every portal: staff / …
```

The window prints the staff password that actually works.

## Options

Add these after the file name in a terminal, for example `start-PC-C.cmd -Fresh`:

| Option | Windows | Mac | What it does |
|---|---|---|---|
| Reload the demo data | `-Fresh` | `--fresh` | Throws away this computer's data and loads the bundle again |
| Stop | `-Stop` | `--stop` | Stops this computer's organisations. The databases keep running in Docker. |

## When it stops with a message

The window says what went wrong and what to do. The common ones:

| Message | Fix |
|---|---|
| `four_pcs.yaml says PC-X is …, but this computer's addresses are …` | The Wi-Fi gave this computer a new address. Correct it in `four_pcs.yaml` on all four computers, then restart all four. |
| `MongoDB refuses the login` | Run `docker compose -f infra/compose/engines.yml down -v`, then start again. The data reloads from the bundle. |
| `bundle … is missing` | Run `git pull`, or copy `infra/out/bundles/<your PC>.zip` from PC-A. |
| `port … is used by another program` | Close that program, then start again. |
| The other computers stay at "waiting for the directory on PC-A" | PC-A is not running, or the Wi-Fi blocks computers from reaching each other. From that computer, `curl http://<PC-A address>:8400/directory/v1/health` should answer. |

Details of each step are in `infra/scripts/start_pc.py`. The full manual procedure is in `docs/runbook/FOUR_PCS.md`.
