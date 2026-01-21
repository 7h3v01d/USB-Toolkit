import usb.core
import usb.util
import json
import time
from datetime import datetime

def find_usb_devices():
    """Find all connected USB devices and return their descriptors."""
    devices = usb.core.find(find_all=True)
    device_info = []
    
    for dev in devices:
        try:
            # Get device descriptor
            info = {
                'timestamp': datetime.now().isoformat(),
                'vendor_id': hex(dev.idVendor),
                'product_id': hex(dev.idProduct),
                'manufacturer': usb.util.get_string(dev, dev.iManufacturer) or 'Unknown',
                'product': usb.util.get_string(dev, dev.iProduct) or 'Unknown',
                'serial_number': usb.util.get_string(dev, dev.iSerialNumber) or 'Unknown',
                'bus': dev.bus,
                'address': dev.address,
                'configuration': dev.bConfigurationValue,
                'device_class': hex(dev.bDeviceClass),
                'device_subclass': hex(dev.bDeviceSubClass),
                'protocol': hex(dev.bDeviceProtocol),
            }
            device_info.append(info)
        except usb.core.USBError as e:
            print(f"Error accessing device {dev}: {e}")
    
    return device_info

def save_device_info(device_info, filename='usb_handshake.json'):
    """Save device information to a JSON file."""
    with open(filename, 'a') as f:
        json.dump(device_info, f, indent=4)
        f.write('\n')

def monitor_usb_ports():
    """Monitor USB ports for device connections."""
    print("Monitoring USB ports... Press Ctrl+C to stop.")
    known_devices = set()
    
    while True:
        try:
            devices = usb.core.find(find_all=True)
            current_devices = set((dev.idVendor, dev.idProduct, dev.address) for dev in devices)
            
            # Detect new devices
            new_devices = current_devices - known_devices
            if new_devices:
                print("New USB device(s) detected!")
                device_info = find_usb_devices()
                save_device_info(device_info)
                print(f"Saved device info to usb_handshake.json: {device_info}")
            
            # Update known devices
            known_devices = current_devices
            time.sleep(1)  # Check every second
        except KeyboardInterrupt:
            print("Stopped monitoring USB ports.")
            break
        except usb.core.USBError as e:
            print(f"USB error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    print("Starting USB handshake capture...")
    monitor_usb_ports()