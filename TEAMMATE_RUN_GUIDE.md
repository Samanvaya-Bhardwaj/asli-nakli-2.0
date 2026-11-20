# Running Asali on your computer

Our project runs on four computers at once. Each computer hosts a few of the twelve organisations: pharma companies,
distributors, shops, the regulator and the consumer check. They find each other on the Wi-Fi. This guide gets your
computer's part running, and then you start it again with one double-click on demo day.

## Which computer are you?

| Computer | Who it runs | Address on the Wi-Fi | Your start file |
|---|---|---|---|
| **PC-A** (Windows) | Directory, regulator, consumer check (Delhi, Mumbai) | 192.168.52.152 | `start-PC-A.cmd` |
| **PC-B** (Mac) | Tarang Pharma, Medivra Labs, Kesar Biologics | 192.168.52.111 | `start-PC-B.command` |
| **PC-C** (Windows) | North Star, Western Medilink, Dakshin (distributors) | 192.168.39.77 | `start-PC-C.cmd` |
| **PC-D** (Windows) | Sharma Medicos, Apna Chemist, Namma Pharmacy (shops) | 192.168.52.155 | `start-PC-D.cmd` |

**PC-A starts first.** It holds the directory that the other three register with. If you start before PC-A, your
window waits for it, and that is fine.

---

## Part 1: one-time setup (do this before demo day)

The first run needs internet and takes about 10 minutes. Later runs take under a minute.

### 1. Install Docker Desktop

The databases run inside Docker.

- **Windows:**
  1. Open PowerShell as administrator and run `wsl --install --no-distribution`.
  2. Restart the computer.
  3. Install Docker Desktop from docker.com, and start it once.
- **Mac:** install Docker Desktop for your chip (Apple silicon or Intel) from docker.com, and start it once.

When Docker Desktop shows "Engine running", you're done. You don't need to open it again: the start file starts it.

### 2. Get the project

You need Git (Windows: `winget install Git.Git`; Mac: it asks to install the command-line tools the first time you use
`git`). Then, in a terminal:

```
git clone https://github.com/Samanvaya-Bhardwaj/asli-nakli-2.0.git
```

Put it in a plain folder such as `C:\asali` or `~/asali`, **not inside OneDrive or iCloud**. Syncing breaks the
environment the start file creates.

No Git? On the GitHub page, click **Code → Download ZIP** and unzip it. That works too.

### 3. Do a first run

Open the `asali-net` folder inside the project and double-click your start file (see the table above). On a Mac, if
double-clicking does nothing or macOS blocks it, right-click it and choose **Open**, or run `bash start-PC-B.command`
in Terminal from that folder.

The first run:

- sets up Python 3.11 by itself. You don't need to install Python.
- loads your computer's demo data.
- asks for network permission:
  - **Windows:** "Allow Python to communicate on these networks?" Tick **both Private and Public**, then click
    **Allow**. If you miss this, the other computers can't reach you.
  - **Mac:** "Do you want python to accept incoming connections?" Click **Allow**.

It worked when the window ends like this:

```
PC-C (your-computer-name, 192.168.39.77) is up. Organisations here:
  North Star Distributors      http://192.168.39.77:8101
  Western Medilink             http://192.168.39.77:8102
  Dakshin Pharma Agencies      http://192.168.39.77:8103
The directory at http://192.168.52.152:8400 lists 12 organisations, 12 online.
Staff login on every portal: staff / bhLlKKepxYwm
Leave this window open. Ctrl+C stops this computer's organisations.
```

Then close the window. That stops it. Setup is done.

---

## Part 2: on demo day

1. Join the **same Wi-Fi** as the other three computers.
2. Turn on **automatic time**:
   - Windows: Settings → Time & language → Date & time → Sync now.
   - Mac: automatic by default.

   Computers whose clocks differ by more than 2 minutes refuse each other's requests.
3. Plug in the charger and turn off sleep, so the computer doesn't drop off the network mid-demo:
   - Windows: Settings → System → Power → Never.
   - Mac: in a spare Terminal window, run `caffeinate -dimsu`.
4. **PC-A first**, then the others: double-click your start file.
5. **Leave the window open** for the whole demo.

**To stop:** close the window, or press Ctrl+C in it.

**Starting it again** is always safe. It keeps your data and clears anything left over from before.

---

## Using the portals

Each organisation has its own website on its own port. They work from any of the four computers.

| Portal | Address |
|---|---|
| Consumer check, Delhi (no login) | http://192.168.52.152:8402 |
| Consumer check, Mumbai (no login) | http://192.168.52.152:8403 |
| Regulator | http://192.168.52.152:8401 |
| Tarang Pharma / Medivra Labs / Kesar Biologics | http://192.168.52.111:8301 / 8302 / 8303 |
| North Star / Western Medilink / Dakshin | http://192.168.39.77:8101 / 8102 / 8103 |
| Sharma Medicos / Apna Chemist / Namma Pharmacy | http://192.168.52.155:8201 / 8202 / 8203 |

**Staff login on every portal:** `staff` / `bhLlKKepxYwm`

**Is everyone online?** Every portal shows "*N* of 12 online" in a corner. Click it to see who is missing.

**Quick test:** open the consumer check and paste `(01)08901001000049(21)TPFDPHACBEE`. With all four computers up,
it answers **Genuine**. If someone is offline, it says **Cannot check**, which is correct behaviour.

**Camera scanning** only works on the computer itself at `http://localhost:<port>`, for example
http://localhost:8402 on PC-A. Over the Wi-Fi address the browser blocks the camera, so type or paste the code instead.

---

## Extra options

Run these from a terminal in the `asali-net` folder:

| What | Windows | Mac |
|---|---|---|
| Start | `.\start-PC-C.cmd` | `bash start-PC-B.command` |
| Throw away your data and load the demo data again | `.\start-PC-C.cmd -Fresh` | `bash start-PC-B.command --fresh` |
| Stop | `.\start-PC-C.cmd -Stop` | `bash start-PC-B.command --stop` |

Use your own computer's file name.

---

## If something goes wrong

The window stops with a message that says what to do. The common ones:

| You see | Do this |
|---|---|
| `four_pcs.yaml says PC-X is …, but this computer's addresses are …` | The Wi-Fi gave you a new address. Tell the team. Everyone updates `asali-net/infra/four_pcs.yaml` to the same new values, then all four restart. Find your address with `ipconfig` (Windows, "IPv4 Address") or `ipconfig getifaddr en0` (Mac). |
| `waiting for the directory on PC-A` and it never moves on | PC-A isn't running, or the Wi-Fi blocks computers from talking to each other. Check that PC-A's window is open. Then in your browser, open http://192.168.52.152:8400/directory/v1/health: it should show `{"status":"ok"}`. If it doesn't, everyone moves to a **phone hotspot** (update the addresses as in the first row). |
| `Docker is not installed` / `Docker Desktop did not become ready` | Install or open Docker Desktop, wait for "Engine running", then start again. |
| `MongoDB refuses the login` | In a terminal in `asali-net`, run `docker compose -f infra/compose/engines.yml down -v`, then start again. Your demo data reloads by itself. |
| `port … is used by another program` | Close that program, or restart the computer, then start again. |
| `the Python environment could not be set up` | Check the internet connection, then start again. The first run downloads Python. |
| Others can't reach your portals, but yours work on your own computer | Your firewall is blocking them. Windows: Settings → Privacy & security → Windows Security → Firewall → Allow an app → find **python** and tick Private and Public. Mac: System Settings → Network → Firewall → allow Python. |
| The window flashes and closes | Open a terminal in `asali-net` and run the start file from there, so you can read the message. |

Still stuck? Send the team a photo of the last lines in the window.
