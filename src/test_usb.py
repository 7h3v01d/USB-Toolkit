import usb.core
import usb.backend.libusb1

backend = usb.backend.libusb1.get_backend()
devices = usb.core.find(find_all=True, backend=backend)
if devices is None:
    print("No USB devices found or backend issue.")
else:
    for dev in devices:
        try:
            print(f"Device: {dev.idVendor:04x}:{dev.idProduct:04x}")
        except Exception as e:
            print(f"Error accessing device: {e}")