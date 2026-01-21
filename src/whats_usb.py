import usb.core
import usb.util
import psutil
import platform
import sys
from datetime import datetime

def get_usb_class_name(class_code):
    """Return a human-readable USB class name based on the class code."""
    usb_classes = {
        0x00: "Per Interface",
        0x01: "Audio",
        0x02: "Communications",
        0x03: "HID (Human Interface Device)",
        0x05: "Physical",
        0x06: "Image",
        0x07: "Printer",
        0x08: "Mass Storage",
        0x09: "Hub",
        0x0A: "CDC-Data",
        0x0B: "Smart Card",
        0x0D: "Content Security",
        0x0E: "Video",
        0x0F: "Personal Healthcare",
        0x10: "Audio/Video Devices",
        0x11: "Billboard Device",
        0xDC: "Diagnostic Device",
        0xE0: "Wireless Controller",
        0xEF: "Miscellaneous",
        0xFE: "Application Specific",
        0xFF: "Vendor Specific"
    }
    return usb_classes.get(class_code, f"Unknown (0x{class_code:02x})")

def get_device_type(device):
    """Determine if the device is a storage device, dongle, or other based on class and characteristics."""
    if device.bDeviceClass == 0x08 or any(cfg.bInterfaceClass == 0x08 for cfg in device):
        return "Mass Storage Device"
    elif device.bDeviceClass == 0x03 or any(cfg.bInterfaceClass == 0x03 for cfg in device):
        return "HID (e.g., Keyboard, Mouse, or Dongle)"
    elif device.bDeviceClass == 0x09:
        return "USB Hub"
    elif device.bDeviceClass == 0xFF:
        return "Vendor-Specific (Possible Dongle or Specialized Device)"
    else:
        return "Other/Unknown Device Type"

def get_firmware_info(device):
    """Attempt to retrieve firmware information (limited by device and permissions)."""
    try:
        # Firmware info is often not directly accessible via standard USB descriptors
        # Some devices expose it through string descriptors or custom control transfers
        firmware_str = usb.util.get_string(device, device.iProduct) or "Not Available"
        return firmware_str
    except Exception as e:
        return f"Not Accessible: {str(e)}"

def get_usb_details(device):
    """Gather comprehensive details about a USB device."""
    details = []
    try:
        details.append(f"Device ID: {device.idVendor:04x}:{device.idProduct:04x}")
        details.append(f"Manufacturer: {usb.util.get_string(device, device.iManufacturer) or 'Unknown'}")
        details.append(f"Product: {usb.util.get_string(device, device.iProduct) or 'Unknown'}")
        details.append(f"Serial Number: {usb.util.get_string(device, device.iSerialNumber) or 'Unknown'}")
        details.append(f"Device Class: {get_usb_class_name(device.bDeviceClass)}")
        details.append(f"Device Type: {get_device_type(device)}")
        details.append(f"Firmware/Product Version: {get_firmware_info(device)}")
        details.append(f"USB Version: {device.bcdUSB:04x}")
        details.append(f"Device Speed: {['Low', 'Full', 'High', 'Super'][device.bDeviceProtocol] if device.bDeviceProtocol < 4 else 'Unknown'}")
        details.append(f"Max Power: {device.bMaxPower * 2}mA" if hasattr(device, 'bMaxPower') else "Max Power: Unknown")
        
        # Configuration details
        for cfg in device:
            details.append(f"\nConfiguration {cfg.bConfigurationValue}:")
            details.append(f"  Total Length: {cfg.wTotalLength} bytes")
            details.append(f"  Number of Interfaces: {cfg.bNumInterfaces}")
            for intf in cfg:
                details.append(f"    Interface {intf.bInterfaceNumber}:")
                details.append(f"      Class: {get_usb_class_name(intf.bInterfaceClass)}")
                details.append(f"      Subclass: 0x{intf.bInterfaceSubClass:02x}")
                details.append(f"      Protocol: 0x{intf.bInterfaceProtocol:02x}")
                for ep in intf:
                    details.append(f"      Endpoint Address: 0x{ep.bEndpointAddress:02x}")
                    details.append(f"      Max Packet Size: {ep.wMaxPacketSize} bytes")
                    details.append(f"      Endpoint Type: {['Control', 'Isochronous', 'Bulk', 'Interrupt'][ep.bmAttributes & 0x03]}")
        
        # Additional system-level info (if available)
        if platform.system() == "Windows":
            details.append(f"OS: {platform.system()} {platform.release()}")
        else:
            details.append(f"OS: {platform.system()} {platform.version()}")

        # Check if device is mounted (for storage devices)
        if get_device_type(device) == "Mass Storage Device":
            partitions = psutil.disk_partitions()
            for part in partitions:
                if "usb" in part.device.lower() or "removable" in part.opts.lower():
                    details.append(f"Mounted at: {part.mountpoint}")
                    usage = psutil.disk_usage(part.mountpoint)
                    details.append(f"  Total Space: {usage.total / (1024**3):.2f} GB")
                    details.append(f"  Used Space: {usage.used / (1024**3):.2f} GB")
                    details.append(f"  Free Space: {usage.free / (1024**3):.2f} GB")
        
    except usb.core.USBError as e:
        details.append(f"Error accessing some details: {str(e)} (Try running with sudo/admin privileges)")
    except Exception as e:
        details.append(f"Unexpected error: {str(e)}")
    
    return "\n".join(details)

def list_usb_devices():
    """List all connected USB devices and return them."""
    devices = list(usb.core.find(find_all=True))
    if not devices:
        print("No USB devices found.")
        return None
    print("\nConnected USB Devices:")
    for i, dev in enumerate(devices, 1):
        try:
            manufacturer = usb.util.get_string(dev, dev.iManufacturer) or "Unknown"
            product = usb.util.get_string(dev, dev.iProduct) or "Unknown"
            print(f"{i}. {manufacturer} - {product} (VendorID: {dev.idVendor:04x}, ProductID: {dev.idProduct:04x})")
        except Exception as e:
            print(f"{i}. Unknown Device (VendorID: {dev.idVendor:04x}, ProductID: {dev.idProduct:04x})")
    return devices

def main():
    print(f"WhatsUSB - USB Device Information Tool (v1.0, {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("---------------------------------------------------")
    
    devices = list_usb_devices()
    if not devices:
        sys.exit(1)
    
    try:
        choice = int(input("\nSelect a device number to view details (or 0 to exit): "))
        if choice == 0:
            print("Exiting...")
            sys.exit(0)
        if choice < 1 or choice > len(devices):
            print("Invalid selection.")
            sys.exit(1)
        
        selected_device = devices[choice - 1]
        print(f"\nDetailed Information for {usb.util.get_string(selected_device, selected_device.iProduct) or 'Unknown Device'}:")
        print("---------------------------------------------------")
        print(get_usb_details(selected_device))
        
    except ValueError:
        print("Please enter a valid number.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        sys.exit(0)