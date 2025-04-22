import cv2
import os
import json
import pytesseract  # pip install pytesseract
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk  # pip install Pillow

# Global variables to store click points, cropped data, and the image
points = []
data_images = []
img = None
POINTS_FILE = "points.json"
data = []

def list_images_in_directory(directory):
    # Define allowed image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}
    images = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in image_extensions:
                images.append(os.path.join(root, file))
    return images

def save_points(filename=POINTS_FILE):
    # Save points as list of lists (JSON doesn't support tuples)
    with open(filename, "w") as f:
        json.dump(points, f)

def load_points(filename=POINTS_FILE):
    global points
    if os.path.exists(filename):
        with open(filename, "r") as f:
            loaded = json.load(f)
            # Convert inner lists to tuples
            points = [tuple(pt) for pt in loaded]
            # print("Loaded saved points:", points)

def detect_text(image):
    # Recognize text from the cropped image using pytesseract
    text = pytesseract.image_to_string(image, lang='eng', config='outputbase digits')
    # print("Detected text:", text)
    return text

def click_event(event, x, y, flags, param):
    global points, img
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        save_points()  # Save points after each click
        print(f"Point selected: ({x}, {y})")
        # Draw a small circle where the user clicked
        cv2.circle(img, (x, y), 5, (0, 255, 0), -1)
        cv2.imshow('Image', img)
        # When two points have been selected, crop the image
        if len(points) % 2 == 0:
            cropped = crop_image(points[-2], points[-1], img, True)
            data_images.append(cropped)
            # Removed text detection here to process after interactive session

def crop_image(pt1, pt2, img, show=False, show_cropped=False):
    # Determine the top-left and bottom-right corners
    x1, y1 = min(pt1[0], pt2[0]), min(pt1[1], pt2[1])
    x2, y2 = max(pt1[0], pt2[0]), max(pt1[1], pt2[1])
    # Draw rectangle on the image between the two points
    if show:
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.imshow('Image', img)
    if show_cropped:
        cv2.imshow('Cropped Image', img[y1:y2, x1:x2])
        cv2.waitKey(0)
    # Crop the image (use copy to ensure the cropped data is independent)
    cropped = img[y1:y2, x1:x2].copy()
    print("Cropped area processed.")
    # Reset points to allow additional crops if needed and clear saved points file
    return cropped

def recognize(image_file_collection):
    # Use Tkinter to create an interface for reviewing each image
    root = tk.Tk()
    root.title("Image Recognition Interface")
    # Set a larger window size
    root.geometry("1200x800")
    
    current_index = 0
    recognized_data = []  # To store the input data for each image
    
    # Create a main frame with two columns: left for image, right for controls
    main_frame = tk.Frame(root)
    main_frame.pack(pady=10, padx=10, fill="both", expand=True)
    
    # Label for displaying the image (left column)
    image_label = tk.Label(main_frame)
    image_label.grid(row=0, column=0, padx=20, pady=10)
    
    # Frame for controls (right column)
    control_frame = tk.Frame(main_frame)
    control_frame.grid(row=0, column=1, padx=20, pady=10, sticky="n")
    
    # Add a checkbox for invalid datapoint
    invalid_var = tk.BooleanVar()
    invalid_checkbox = tk.Checkbutton(control_frame, text="Invalid datapoint", variable=invalid_var)
    invalid_checkbox.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
    
    # Textboxes for data, starting from row 1
    tk.Label(control_frame, text="Volume:").grid(row=1, column=0, sticky="w", pady=5)
    vol_entry = tk.Entry(control_frame, width=20)
    vol_entry.grid(row=1, column=1, pady=5)
    
    tk.Label(control_frame, text="Diameter:").grid(row=2, column=0, sticky="w", pady=5)
    dia_entry = tk.Entry(control_frame, width=20)
    dia_entry.grid(row=2, column=1, pady=5)
    
    tk.Label(control_frame, text="Amplitude:").grid(row=3, column=0, sticky="w", pady=5)
    amp_entry = tk.Entry(control_frame, width=20)
    amp_entry.grid(row=3, column=1, pady=5)
    
    tk.Label(control_frame, text="Width:").grid(row=4, column=0, sticky="w", pady=5)
    width_entry = tk.Entry(control_frame, width=20)
    width_entry.grid(row=4, column=1, pady=5)
    
    tk.Label(control_frame, text="Frequency:").grid(row=5, column=0, sticky="w", pady=5)
    freq_entry = tk.Entry(control_frame, width=20)
    freq_entry.grid(row=5, column=1, pady=5)
    
    # Next Image button below the textboxes & checkbox area
    next_button = tk.Button(control_frame, text="Next Image")
    next_button.grid(row=6, column=0, columnspan=2, pady=10)
    
    # Variable to hold ImageTk.PhotoImage reference
    photo = None

    def show_image(index):
        nonlocal photo
        # Load the image using cv2 and convert it for Tkinter
        img_cv = cv2.imread(image_file_collection[index])
        if img_cv is None:
            print(f"Error loading image: {image_file_collection[index]}")
            return
        
        # Process cropped areas from loaded points
        processed_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        data_cur_img = []
        for i in range(int(len(points)/2)):
            pt1 = points[i*2]
            pt2 = points[i*2 + 1]
            cropped = crop_image(pt1, pt2, processed_img, False, False)
            text = detect_text(cropped)
            text = text.replace("\n", "")
            data_cur_img.append(text)
        
        image_name = os.path.basename(image_file_collection[index])
        data_cur_img.append(image_name)
        try:
            if float(data_cur_img[0]) > 100:
                data_cur_img[0] = str(float(data_cur_img[0]) / 10)
            if float(data_cur_img[1]) > 100:
                data_cur_img[1] = str(float(data_cur_img[1]) / 10)
        except:
            print("Error converting to float, skipping conversion")
        # Save the detected data for display (will be overwritten by manual input)
        data.append(data_cur_img)
        print(data_cur_img)
        # For display, convert image to RGB and a larger size
        img_cv_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_cv_rgb)
        pil_img = pil_img.resize((800, 600))
        photo = ImageTk.PhotoImage(pil_img)
        image_label.config(image=photo)
        # Clear previous entries and fill with data_cur_img if available
        vol_entry.delete(0, tk.END)
        dia_entry.delete(0, tk.END)
        amp_entry.delete(0, tk.END)
        width_entry.delete(0, tk.END)
        freq_entry.delete(0, tk.END)
        if len(data_cur_img) >= 5:
            vol_entry.insert(0, data_cur_img[0])
            dia_entry.insert(0, data_cur_img[1])
            amp_entry.insert(0, data_cur_img[2])
            width_entry.insert(0, data_cur_img[3])
            freq_entry.insert(0, data_cur_img[4])
        # Reset the checkbox for each new image
        invalid_var.set(False)

    def next_image():
        nonlocal current_index
        # Save the entered data for the current image along with the checkbox state
        entry_data = [
            vol_entry.get(),
            dia_entry.get(),
            amp_entry.get(),
            width_entry.get(),
            freq_entry.get(),
            os.path.basename(image_file_collection[current_index]),
            "Invalid" if invalid_var.get() else "Valid"
        ]
        recognized_data.append(entry_data)
        
        current_index += 1
        with open('data.csv', 'w') as f:
            for d in recognized_data:
                f.write(",".join(d) + "\n")
        print("Data saved to data.csv")
        if current_index < len(image_file_collection):
            show_image(current_index)
        else:
            print("All images processed.")
            root.destroy()
    
    next_button.config(command=next_image)
    show_image(current_index)
    root.mainloop()

if __name__ == '__main__':
    # Load saved points (if any)
    load_points()
    
    # List all images in the current directory and its subdirectories
    current_directory = os.getcwd()
    image_files = list_images_in_directory(current_directory)
    
    # Replace with your image file path if desired, or choose one from the list above
    img_path = image_files[0] if image_files else None
    if not img_path or not os.path.exists(img_path):
        print("Image file not found!")
        exit(1)
    
    # If points are loaded, ask the user if they want to mark these points again.
    if points:
        choice = input(f"Loaded saved points {points}. Mark these points again? (Y/N): ")
        if choice.upper() == "Y":
            points.clear()
            print("Interactive marking.")
        else:
            print("Continuing with loaded points.")
            recognize(image_files)
            exit(0)
            
    img = cv2.imread(img_path)
    cv2.imshow('Image', img)
    cv2.setMouseCallback('Image', click_event)
    print("Click two points on the image to crop the desired area.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # After interactive marking, call recognize function to show interface for manual text input
    recognize(image_files)
