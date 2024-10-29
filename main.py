from typing import Union, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from serial.tools import list_ports
from pydobot import Dobot
from pyzbar.pyzbar import decode
import cv2
import numpy as np
from typing import Optional
import time
import sqlite3
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime


app = FastAPI()

class StorageRequest(BaseModel):
    zone_id: str
    productType: str
    additionalInfo: str

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize SQLite Database with zones and coordinates
def initialize_database():
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()

    # Create coordinates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coordinates (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            x REAL,
            y REAL,
            z REAL
        )
    ''')

    # Create zones table with additional columns for productType and additionalInfo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            x REAL,
            y REAL,
            z REAL,
            status TEXT,
            productCode TEXT,
            productType TEXT,
            additionalInfo TEXT,
            datetime TEXT
        )
    ''')

    # Insert default coordinates for pickup, drop, and safe zones
    coordinates_data = [
        ("pickup_zone", -10.702980995178223, -292.842529296875, -77.93537902832031),
        ("drop_zone", -14.7539701461792, 226.28904724121094, -71.42035675048828),
        ("safe_zone", 247.40579223632812, -0.2371116727590561, 126.39020538330078)
    ]
    cursor.executemany("INSERT OR IGNORE INTO coordinates (name, x, y, z) VALUES (?, ?, ?, ?)", coordinates_data)

    # Insert default zones for storage with new columns for productType and additionalInfo
    zones_data = [
        ("A1", 285.9593200683594, 108.25691223144531, -72, "available", None, None, None, None),
        ("A2", 285.9593200683594, -3.4887490272521973, -72, "available", None, None, None, None),
        ("A3", 285.9593200683594, -103.77864074707031, -72, "available", None, None, None, None),
        ("B1", 190.71324157714844, 103.214599609375, -72, "available", None, None, None, None),
        ("B3", 190.71324157714844, -114.82876586914062, -72, "available", None, None, None, None)
    ]
    cursor.executemany("INSERT OR IGNORE INTO zones (name, x, y, z, status, productCode, productType, additionalInfo,datetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?,?)", zones_data)

    conn.commit()
    conn.close()

initialize_database()

def get_coordinate(name: str):
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, z FROM coordinates WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"x": row[0], "y": row[1], "z": row[2]}
    else:
        raise HTTPException(status_code=404, detail=f"Coordinate '{name}' not found.")

def get_zone(zone_id: str):
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()
    cursor.execute("SELECT x, y, z, status, productCode, productType, additionalInfo FROM zones WHERE name = ?", (zone_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "x": row[0],
            "y": row[1],
            "z": row[2],
            "status": row[3],
            "productCode": row[4],
            "productType": row[5],
            "additionalInfo": row[6]
        }
    else:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")


def update_zone_status(zone_id: str, status: str):
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE zones SET status = ? WHERE name = ?", (status, zone_id))
    conn.commit()
    conn.close()


# Default speed parameters (adjust as needed)
DEFAULT_VELOCITY = 50  # Set a lower value for slower speed (e.g., 50)
DEFAULT_ACCELERATION = 50  # Set a lower value for slower acceleration (e.g., 50)

# Global variable to store the Dobot device and a flag to track connection status
device = None
is_connected = False  # Flag to track connection status

# Function to connect to Dobot and store the device globally
def connect_to_dobot():
    global device, is_connected  # Use the global 'device' and 'is_connected' variables
    
    # If the device is already connected, skip reconnection
    if is_connected and device:
        return device, "Dobot is already connected."

    available_ports = list_ports.comports()
    
    # Check if any ports are available
    if not available_ports:
        return None, "No available serial ports found. Make sure Dobot is connected."

    # Print the available ports for debugging purposes
    print("Available ports:", [port.device for port in available_ports])

    # Get the first available port
    port = available_ports[0].device
    print(f"Trying to connect to Dobot on port: {port}")

    try:
        # Attempt to create the Dobot object
        device = Dobot(port=port)
        
        # Check if Dobot was successfully created
        if device is None:
            return None, "Failed to create Dobot instance. The connection may not be established."

        is_connected = True  # Set the connection flag to True
        return device, "Dobot connected successfully!"
    except AttributeError as attr_err:
        return None, f"Attribute error while connecting to Dobot: {attr_err}"
    except Exception as e:
        return None, f"Failed to connect to Dobot: {e}"

# Function to set the speed of the Dobot
def set_dobot_speed(velocity: float = DEFAULT_VELOCITY, acceleration: float = DEFAULT_ACCELERATION):
    """Set the speed and acceleration of the Dobot."""
    global device
    if device:
        device.speed(velocity, acceleration)
        print(f"Dobot speed set to velocity: {velocity}, acceleration: {acceleration}")
    else:
        print("Dobot is not connected. Cannot set speed.")

# FastAPI event handler to run on startup
@app.on_event("startup")
async def startup_event():
    global device
    device, message = connect_to_dobot()
    if device:
        print("Dobot connected successfully on startup!")
        set_dobot_speed()  # Set default speed on startup
    else:
        print(f"Failed to connect Dobot on startup: {message}")

# FastAPI event handler to run on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    global device, is_connected
    if device:
        print("Disconnecting Dobot on shutdown...")
        device.close()
        device = None  # Reset the device
        is_connected = False  # Reset the connection flag
        print("Dobot disconnected successfully.")

@app.get("/")
def read_root():
    return {"message": "FastAPI server is running"}

@app.post("/set-home")
def set_home_position():
    global device  # Ensure we're using the global 'device' variable

    # Ensure Dobot is connected
    if not device:
        return {"status": "error", "message": "Dobot is not connected. Please connect first."}

    try:
        # Call the command to set the home position
        device._set_home_cmd()
        return {"status": "success", "message": "Home position set successfully."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to set home position: {e}"}


@app.get("/set-speed")
def set_speed_endpoint(velocity: float = DEFAULT_VELOCITY, acceleration: float = DEFAULT_ACCELERATION):
    """Endpoint to set Dobot speed."""
    set_dobot_speed(velocity, acceleration)
    return {"status": "success", "message": f"Dobot speed set to velocity: {velocity}, acceleration: {acceleration}"}

@app.get("/dobot-status")
def check_dobot_connection():
    global device  # Ensure we're using the global 'device' variable
    if device:
        return {"status": "success", "message": "Dobot is connected."}
    else:
        return {"status": "error", "message": "Dobot is not connected."}

@app.get("/dobot-position")
def get_dobot_position():
    global device  # Ensure we're using the global 'device' variable
    # Ensure Dobot is connected
    if not device:
        return {"status": "error", "message": "Dobot is not connected. Please connect first."}
    
    try:
        # Get the current pose of the Dobot
        pose = device.get_pose()

        # Access the attributes from the nested Position and Joints objects
        position = pose.position  # Get the Position object
        joints = pose.joints  # Get the Joints object

        # Return the position and joint information
        return {
            "status": "success",
            "x": position.x,
            "y": position.y,
            "z": position.z,
            "r": position.r,
            "joint1": joints.j1,
            "joint2": joints.j2,
            "joint3": joints.j3,
            "joint4": joints.j4,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get Dobot position: {e}"}


@app.get("/move-to/")
def move_dobot_to(x: float, y: float, z: float, r: Optional[float] = 0, velocity: float = DEFAULT_VELOCITY, acceleration: float = DEFAULT_ACCELERATION):
    global device  # Ensure we're using the global 'device' variable
    # Ensure Dobot is connected
    if not device:
        return {"status": "error", "message": "Dobot is not connected. Please connect first."}

    try:
        # Set the desired speed before movement
        set_dobot_speed(velocity, acceleration)
        
        # Move Dobot to the specified position
        device.move_to(x, y, z, r)
        return {"status": "success", "message": f"Moved Dobot to position ({x}, {y}, {z}, {r}) with velocity: {velocity} and acceleration: {acceleration}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to move Dobot: {e}"}


@app.post("/pickup-from-store/")
def pickup_from_store_operation(zone_id: str, velocity: float = DEFAULT_VELOCITY, acceleration: float = DEFAULT_ACCELERATION):
    global device  # Ensure we're using the global 'device' variable

    # Retrieve storage zone details from the database
    zone = get_zone(zone_id)
    if zone["status"] != "occupied":
        raise HTTPException(status_code=400, detail=f"Zone {zone_id} is not occupied. No package to pick up.")

    # Retrieve safe and drop zone coordinates
    safe_zone = get_coordinate("safe_zone")
    drop_zone = get_coordinate("drop_zone")

    try:
        # Step 1: Set speed
        set_dobot_speed(velocity, acceleration)

        # Step 2: Move to the safe zone before interacting with the storage zone
        device.move_to(safe_zone["x"], safe_zone["y"], safe_zone["z"], 0)
        print(f"Moved to safe zone {safe_zone} before interacting with storage zone.")

        # Step 3: Move to the storage zone (along z-axis)
        z_up_store = zone["z"] + 110  # Move to a position above the storage zone
        device.move_to(zone["x"], zone["y"], z_up_store, 0)  # Move above the storage zone
        device.move_to(zone["x"], zone["y"], zone["z"], 0)  # Move down into the storage zone
        device.suck(True)  # Activate suction to pick up the package
        print(f"Picked up package from storage zone {zone_id} at ({zone['x']}, {zone['y']}, {zone['z']})")

        # Step 4: Move up for safety after picking up the package
        device.move_to(zone["x"], zone["y"], z_up_store, 0)  # Move back up to a safe height
        print(f"Moved up to a safe height after picking up the package from storage zone.")

        # Step 5: Move to the drop zone (along z-axis)
        z_above_drop = drop_zone["z"] + 110  # Move to a position above the drop zone
        device.move_to(drop_zone["x"], drop_zone["y"], z_above_drop, 0)  # Move above the drop zone
        device.move_to(drop_zone["x"], drop_zone["y"], drop_zone["z"], 0)  # Move down into the drop zone
        device.suck(False)  # Deactivate suction to drop the package
        print(f"Dropped package at drop zone at ({drop_zone['x']}, {drop_zone['y']}, {drop_zone['z']})")

        # Step 6: Move back up for safety after dropping the package
        device.move_to(drop_zone["x"], drop_zone["y"], z_above_drop, 0)
        print(f"Moved back up to a safe height after dropping the package.")

        # Step 7: Move back to the safe zone after dropping the package
        device.move_to(safe_zone["x"], safe_zone["y"], safe_zone["z"], 0)
        print(f"Moved back to safe zone {safe_zone} after dropping the package.")

        # Step 8: Update the zone's status to "available" and clear additional data
        conn = sqlite3.connect("robot_zones.db")
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE zones
            SET status = "available", productCode = NULL, productType = NULL, additionalInfo = NULL, datetime = NULL
            WHERE name = ?
        ''', (zone_id,))
        conn.commit()
        conn.close()

        return {"status": "success", "message": f"Package picked up from {zone_id} and dropped at the drop zone."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to complete operation: {e}"}
    
@app.post("/storage/")
def storage_operation(request: StorageRequest, max_barcode_attempts: Optional[int] = 3, velocity: float = DEFAULT_VELOCITY, acceleration: float = DEFAULT_ACCELERATION):
    zone_id = request.zone_id
    productType = request.productType
    additionalInfo = request.additionalInfo
    global device  # Ensure we're using the global 'device' variable

    # Get pickup and safe zone coordinates from the database
    pickup_zone = get_coordinate("pickup_zone")
    safe_zone = get_coordinate("safe_zone")
    
    # Retrieve the specified storage zone data
    zone = get_zone(zone_id)
    if zone["status"] != "available":
        raise HTTPException(status_code=400, detail=f"Zone {zone_id} is not available.")

    # Step 1: Attempt to read the barcode
    print("Attempting to read barcode before storing the package.")
    barcode_data = barcode_reader_and_handle_package(max_attempts=max_barcode_attempts)
    if not barcode_data:
        print(f"No barcode detected after {max_barcode_attempts} attempts. Operation canceled.")
        return JSONResponse(content={"status": "error", "message": f"No barcode detected after {max_barcode_attempts} attempts."}, status_code=404)

    # Retrieve the barcode data
    product_code = barcode_data[0]['data']  # Use the first detected barcode

    # Step 2: Update the zone with the captured `product_code`, `productType`, `additionalInfo`, and current datetime
    current_datetime = datetime.now().isoformat()  # Get the current date and time
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE zones
        SET productCode = ?, productType = ?, additionalInfo = ?, status = "occupied", datetime = ?
        WHERE name = ?
    ''', (product_code, productType, additionalInfo, current_datetime, zone_id))
    conn.commit()
    conn.close()

    # Step 3: Perform the storage operation
    set_dobot_speed(velocity, acceleration)
    device.move_to(safe_zone["x"], safe_zone["y"], safe_zone["z"], 0)
    
    # Pickup operations
    z_above_pickup = pickup_zone["z"] + 150
    device.move_to(pickup_zone["x"], pickup_zone["y"], z_above_pickup, 0)
    device.move_to(pickup_zone["x"], pickup_zone["y"], pickup_zone["z"], 0)
    device.suck(True)
    device.move_to(pickup_zone["x"], pickup_zone["y"], z_above_pickup)

    # Storage operations
    z_up_store = zone["z"] + 110
    device.move_to(zone["x"], zone["y"], z_up_store, 0)
    device.move_to(zone["x"], zone["y"], zone["z"], 0)
    device.suck(False)
    device.move_to(zone["x"], zone["y"], z_up_store)
    device.move_to(safe_zone["x"], safe_zone["y"], safe_zone["z"], 0)

    return {"status": "success", "message": f"Package stored in zone {zone_id} with type {productType} and additional info {additionalInfo}."}


rotation_angle = 90  # Fixed rotation angle
initial_r = 50  # Fixed rotation value for all operations

# Function to capture barcode from webcam and handle package if not found
def barcode_reader_and_handle_package(max_attempts: int = 50, delay: float = 10):
    global device  # Assuming the Dobot is connected

    if not device:
        raise HTTPException(status_code=500, detail="Dobot is not connected. Please connect first.")

    # Open the webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not open the webcam")

    barcode_data_list = []

    try:
        # Retrieve pickup_zone coordinates from the database
        pickup_zone = get_coordinate("pickup_zone")
        x_pickup, y_pickup, z_pickup = pickup_zone["x"], pickup_zone["y"], pickup_zone["z"]

        # Capture frames and attempt to read barcodes and move the package
        for attempt in range(max_attempts):
            time.sleep(delay)  # Delay before trying again
            detected_barcodes = []  # Reset in each attempt

            # Read and process frames from the webcam
            for i in range(100):
                ret, frame = cap.read()
                if not ret:
                    raise HTTPException(status_code=500, detail="Failed to capture image from webcam")

                detected_barcodes_temp = decode(frame)
                if detected_barcodes_temp:
                    detected_barcodes = detected_barcodes_temp
                    break  # Exit loop if barcode is detected

            if detected_barcodes:
                # Process each detected barcode
                for barcode in detected_barcodes:
                    (x, y, w, h) = barcode.rect
                    cv2.rectangle(frame, (x-10, y-10), (x + w+10, y + h+10), (255, 0, 0), 2)
                    barcode_data = {"data": barcode.data.decode('utf-8'), "type": barcode.type}
                    barcode_data_list.append(barcode_data)

                cv2.imshow("Barcode Detection", frame)
                cv2.waitKey(1000)  # Show the frame for 1 second

                # Move the robot arm up a little before storing the package
                z_up_safe = z_pickup + 50
                device.move_to(x_pickup, y_pickup, z_up_safe, 0)  # Move up slightly before continuing
                return barcode_data_list  # Return as soon as barcode is detected

            # If no barcode is found, move and handle the package
            print(f"Barcode not found. Attempting to pick up and handle package (Attempt {attempt + 1}/{max_attempts})")
            move_and_handle_package(attempt)

        return None  # Return None if no barcode detected after max attempts

    finally:
        cap.release()
        cv2.destroyAllWindows()


# Function to move the Dobot and handle package operations without rotation
def move_and_handle_package(attempt: int):
    global device  # Assuming the Dobot is connected

    try:
        current_r = initial_r  # Use fixed r

        # Retrieve pickup_zone coordinates from the database
        pickup_zone = get_coordinate("pickup_zone")
        x_pickup, y_pickup, z_pickup = pickup_zone["x"], pickup_zone["y"], pickup_zone["z"]
        z_above_pickup = z_pickup + 150  # Move to a position above the pickup zone

        # Move above the pickup zone, pick up, and handle the package
        device.move_to(x_pickup, y_pickup, z_above_pickup, current_r)
        device.move_to(x_pickup, y_pickup, z_pickup, current_r)
        device.suck(True)  # Pickup the package
        device.move_to(x_pickup, y_pickup, z_above_pickup, current_r)
        device.move_to(x_pickup, y_pickup, z_above_pickup, current_r - rotation_angle)
        print(f"Picked up package in attempt {attempt+1} with fixed r={current_r}.")

        # Move down to place the package
        device.move_to(x_pickup, y_pickup, z_pickup, current_r - rotation_angle)
        device.suck(False)  # Drop the package

        return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move or handle the package: {e}")

@app.get("/zones/")
def get_zones():
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, x, y, z, status, productCode, productType, additionalInfo, datetime FROM zones")
    rows = cursor.fetchall()
    conn.close()
    
    # Format the data into a list of dictionaries for easy access on the frontend
    zones_data = []
    for row in rows:
        zones_data.append({
            "name": row[0],
            "x": row[1],
            "y": row[2],
            "z": row[3],
            "status": row[4],
            "productCode": row[5],
            "productType": row[6],
            "additionalInfo": row[7],
            "datetime": row[8]
        })
    
    return {"zones": zones_data}

@app.get("/available-zones/")
def get_available_zones():
    conn = sqlite3.connect("robot_zones.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM zones WHERE status = 'available'")
    rows = cursor.fetchall()
    conn.close()
    
    available_zones = [row[0] for row in rows]  # Extract zone names
    return {"available_zones": available_zones}