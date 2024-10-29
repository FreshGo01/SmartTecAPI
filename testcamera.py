from pyzbar.pyzbar import decode
import cv2

def main():
    # Open the webcam (0 is the default camera)
    cap = cv2.VideoCapture(0)

    # Check if the webcam is opened correctly
    if not cap.isOpened():
        print("Error: Could not open the webcam.")
        return

    while True:
        # Capture frame-by-frame
        ret, frame = cap.read()

        if not ret:
            print("Error: Failed to grab a frame.")
            break

        # Decode barcodes in the frame
        detected_barcodes = decode(frame)

        # Loop through the detected barcodes
        for barcode in detected_barcodes:
            # Get the bounding box of the barcode
            (x, y, w, h) = barcode.rect

            # Draw a rectangle around the barcode
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # Extract the barcode data
            barcode_data = barcode.data.decode('utf-8')
            barcode_type = barcode.type

            # Display the barcode data and type on the frame
            text = f"{barcode_data} ({barcode_type})"
            cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            print(f"Detected barcode: {barcode_data}, Type: {barcode_type}")

        # Display the frame with detected barcodes
        cv2.imshow('Webcam Test with Barcode', frame)

        # Press 'q' to exit the loop
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the webcam and close windows
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
