# USB Toolkit: WhatsUSB & Handshake Capture

## Description
The USB Toolkit is a modular set of tools found in the archives that simplifies the often-opaque world of USB device communication. At its core is WhatsUSB, a comprehensive inspector that translates raw hex codes into human-readable information, such as device classes (HID, Mass Storage, etc.) and specific endpoint configurations. Complementing this is a Handshake Capture monitor that "listens" for new device connections, automatically recording their descriptors into a JSON database for later analysis. Whether you are troubleshooting a custom hardware project, auditing connected peripherals, or verifying libusb backend configurations, this toolkit offers a professional-grade window into your system's USB bus.

---

⚠️ **LICENSE & USAGE NOTICE — READ FIRST**

This repository is **source-available for private technical evaluation and testing only**.

- ❌ No commercial use  
- ❌ No production use  
- ❌ No academic, institutional, or government use  
- ❌ No research, benchmarking, or publication  
- ❌ No redistribution, sublicensing, or derivative works  
- ❌ No independent development based on this code  

All rights remain exclusively with the author.  
Use of this software constitutes acceptance of the terms defined in **LICENSE.txt**.

---

## Key Features

- WhatsUSB - Detailed Device Inspector:
  - Human-Readable Parsing: Converts cryptic class codes into clear categories like "HID (Human Interface Device)", "Audio", or "Mass Storage".
  - Full Descriptor Walkthrough: Displays detailed configuration data, including interface numbers, endpoint addresses, max packet sizes, and endpoint types (Bulk, Interrupt, etc.).
  - Power & Speed Detection: Reports the device's USB version, operating speed, and maximum power draw in milliamps.
  - Storage Intelligence: Automatically detects if a device is a Mass Storage unit and uses psutil to report mount points and available disk space.
- Real-Time Handshake Capture:
  - Continuous Monitoring: Polling-based monitor that detects the exact moment a new device is plugged into the system.
  - Automatic Logging: Instantly captures and appends new device info—including serial numbers and manufacturer strings—to a usb_handshake.json file.
- Diagnostic Connectivity Test: A lightweight script to verify that your Python environment, pyusb library, and libusb backend are correctly configured and communicating with your hardware.
- Cross-Platform Awareness: Integrated OS detection to provide tailored system-level information for both Windows and Unix-based environments.

## Installation

**Prerequisites**
- Python 3.x
- libusb: This backend must be installed on your system for pyusb to function.
  - Windows: Recommended via Zadig or a standard libusb-1.0.dll.
  - Linux/macOS: brew install libusb or sudo apt install libusb-1.0-0.

## Setup

Clone the repository:
```Bash
git clone https://github.com/yourusername/usb-toolkit.git
```
cd usb-toolkit
Install Python dependencies:
```Bash
pip install pyusb psutil
```
---

## Usage
1. Test Connectivity
Ensure your backend is working and list basic device IDs:

```Bash
python test_usb.py
```
2. Inspect a Device (WhatsUSB)
Run the interactive inspector to view detailed specs of a specific device:

```Bash
python whats_usb.py
```
Note: On Linux/macOS, you may need to run this with sudo to access certain descriptors.

---

## 3. Monitor Connections
Start the background listener to log every USB device "handshake":

```Bash
python usb_handshake_capture.py
```
---

## Project Structure

- whats_usb.py: The flagship diagnostic tool for deep device inspection.
- usb_handshake_capture.py: A monitoring script for real-time connection logging to JSON.
- test_usb.py: A simple utility to verify libusb backend functionality.

## Contribution Policy

Feedback, bug reports, and suggestions are welcome.

You may submit:

- Issues
- Design feedback
- Pull requests for review

However:

- Contributions do not grant any license or ownership rights
- The author retains full discretion over acceptance and future use
- Contributors receive no rights to reuse, redistribute, or derive from this code

---

## License
This project is not open-source.

It is licensed under a private evaluation-only license.
See LICENSE.txt for full terms.
