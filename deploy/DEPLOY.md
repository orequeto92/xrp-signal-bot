# Deploy 24/7 on a free Oracle Cloud VM

Run the bot forever on a small **Always Free** virtual machine — no cost, no need to
keep your own PC on. It runs as a `systemd` service that auto-starts on boot and
auto-restarts if it ever crashes.

The bot uses **outbound** connections only (long-polling), so you do **not** need to
open any inbound ports or touch the VM firewall.

## 1. Create the free VM

1. Sign up at **[cloud.oracle.com](https://cloud.oracle.com)** (Always Free tier).
2. **Create a Compute instance:**
   - Image: **Ubuntu 22.04**
   - Shape: pick an **"Always Free eligible"** one
     (`VM.Standard.A1.Flex` ARM, or `VM.Standard.E2.1.Micro` AMD).
   - Add your **SSH public key** (so you can log in).
3. Note the VM's **public IP** and connect:
   ```
   ssh ubuntu@YOUR_VM_IP
   ```

## 2. Install the bot

Python 3 is already on Ubuntu; there are no other dependencies.

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/YOURUSER/xrp-signal-bot.git
cd xrp-signal-bot
cp config.example.py config.py
nano config.py        # paste your TELEGRAM_TOKEN, ALLOWED_CHAT_IDS, BALANCE_COINS
```

`config.py` lives only on the VM (it is gitignored), so your token stays private.

## 3. Install the service

```bash
sudo cp deploy/xrp-signal-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xrp-signal-bot
```

> Using an **Oracle Linux** image instead of Ubuntu? Edit the service file first and
> change `User=ubuntu` and the two `/home/ubuntu/...` paths to `opc` / `/home/opc/...`.

## 4. Check it's alive

```bash
systemctl status xrp-signal-bot        # should say "active (running)"
journalctl -u xrp-signal-bot -f        # live logs (Ctrl+C to exit)
```

Now message your bot `/help` from Telegram — it answers even with your PC off. 🎉

## Managing it

```bash
sudo systemctl restart xrp-signal-bot   # after editing config.py
sudo systemctl stop xrp-signal-bot      # pause it
git pull && sudo systemctl restart xrp-signal-bot   # update to the latest code
```

Your balance/trade log lives in `data/state.json` **on the VM** (also gitignored).
Back it up if you care about the history.
