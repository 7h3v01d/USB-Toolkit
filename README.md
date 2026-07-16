# USB Toolkit

A USB descriptor inspector and handshake-capture monitor with a chain-hashed
audit log — one PyQt6 desktop application in a dark-industrial style.

Copyright 2026 Leon Priest (7h3v01d). Private Evaluation & Testing License
(PETL) v1.0 — see `LICENSE.txt`. Not open-source.

---

## What it does

Three loose scripts, unified into one app with a shared, correct core:

- **Inspector** — pick any connected device and read its full descriptor tree:
  identity, class, USB version, link speed, per-configuration power draw, and
  every interface and endpoint, all decoded into plain language. Vendor and
  product names are resolved from a bundled `usb.ids` database.
- **Monitor** — a background poller that detects every connect *and* disconnect
  and writes each one to an append-only, tamper-evident audit log. Live events
  stream into a table as they happen.
- **Self-Test** — confirms the pyusb + libusb backend is present and can
  enumerate the bus, and reports what `usb.ids` resolved.

If libusb isn't installed, the app still launches against a small demo device
set so you can see the interface before wiring up hardware.

---

## Architecture

Everything above the backend speaks only in plain dataclasses
(`core.models`); nothing else imports pyusb. That single seam is what makes the
whole app testable without hardware and immune to libusb being absent.

```
src/usb_toolkit/
├── app.py                # QApplication bootstrap, backend selection
├── monitor.py            # QThread poller (GC-safe _worker_refs, @pyqtSlot)
├── core/
│   ├── models.py         # Endpoint / Interface / Configuration / UsbDevice
│   ├── decode.py         # human-readable descriptor interpretation
│   ├── backend.py        # UsbBackend + PyusbBackend + MockBackend
│   ├── events.py         # snapshot diff -> connect/disconnect events
│   ├── audit.py          # chain-hashed JSONL log + verify()
│   └── ids.py            # usb.ids vendor/product resolver
└── ui/
    ├── theme.py          # obsidian / teal / phosphor QSS
    ├── inspector.py      ├── monitor_view.py
    ├── selftest.py       └── main_window.py
```

---

## Bugs fixed from the original scripts

- **Device-type detection** read `bInterfaceClass` off a *configuration* object,
  which raised and silently degraded classification. It now walks
  configuration → interface correctly.
- **"Speed"** was derived from `bDeviceProtocol`, which is not speed. Link speed
  is now read from the backend's speed enum and decoded separately.
- **Max power** was read as a *device* field; it's a *configuration* field, and
  is now reported per configuration.
- **The handshake logger** wrote a fresh JSON array on every event and appended
  a newline, producing a file no parser could load. It's now valid JSON Lines,
  chain-hashed, and it logs only the actual delta — including disconnects.

---

## Install & run (Windows)

```
setup.bat      :: creates .venv and installs the package
run.bat        :: launches the GUI (also self-heals the venv on first run)
```

Or manually, from the project root:

```
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m usb_toolkit
```

### libusb backend

pyusb needs a libusb backend to talk to the bus. On Windows, install
`libusb-1.0.dll` (a copy is in `assets/libusb-1.0.rar`) or bind a device with
Zadig. On Linux/macOS: `sudo apt install libusb-1.0-0` / `brew install libusb`.
Some descriptors require admin/sudo to read.

---

## The audit log

The monitor appends to `~/.usb_toolkit/usb_handshake.jsonl`. Each line is one
JSON record:

```
{"prev_hash": "...", "payload": { ... }, "hash": "..."}
```

where `hash = SHA-256(prev_hash + canonical(payload))` and the first record
chains from 64 zeros. Any edit, deletion, or reordering breaks the chain and is
caught by **Verify Log** (or `AuditLog.verify()`). Appends are flushed and
fsync'd; the rare full rewrite (`compact`) goes through a temp file + atomic
replace.

---

## Tests

```
python -m pytest -q
```

29 tests covering decode correctness (the fixed bugs are pinned as regression
tests), the event diff engine, the audit chain including tamper and deletion
detection, the usb.ids parser, backend behaviour, and headless UI construction.
The suite runs entirely against the mock backend — validate on real hardware
by plugging devices with the Monitor running.

---

## `usb.ids`

`assets/usb.ids` is the public USB ID database (linux-usb.org format). If it's
missing, name resolution degrades gracefully to descriptor strings — nothing
breaks. Drop in a newer copy any time to refresh vendor names.
