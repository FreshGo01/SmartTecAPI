from pydobot import Dobot
from serial.tools import list_ports

# Get the available serial ports
available_ports = list_ports.comports()
port = available_ports[0].device if available_ports else None

if not port:
    print("No available serial ports found.")
    exit()

try:
    # Connect to the Dobot using the first available port
    device = Dobot(port=port)
    print("Dobot connected successfully!")

    # Set the home position of the Dobot (optional)
    device._set_home_cmd()

    # Use the set_ptp_cmd to move the Dobot to a specific point (x, y, z)
    # The `mode` argument specifies the motion type (0: Jump mode, 1: MovJ mode, 2: MovL mode)
    # Modify the coordinates and mode as per your requirements
    # Remove `rHead` as it is not a valid parameter in _set_ptp_cmd
    device._set_ptp_cmd(mode=1, x=250, y=0, z=50)  # Example coordinates

    # Check available methods of the Dobot instance
    methods = dir(device)
    print("Available methods in Dobot class:")
    print(Dobot.__version__)
    for method in methods:
        print(method)

except Exception as e:
    print(f"Error connecting to Dobot: {e}")
finally:
    # Make sure to close the device connection safely
    if 'device' in locals():
        device.close()
