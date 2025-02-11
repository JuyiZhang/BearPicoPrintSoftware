import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import ezdxf
import numpy as np
import zipfile
import os
import cv2
from PIL import Image, ImageTk
from ttkthemes import ThemedTk

def start_print():
    print("Starting print...")

def print_input():
    user_input = entry1.get()
    print(user_input)

def open_file_dialog():
    file_path = filedialog.askopenfilename(filetypes=[("DXF and B3P files", "*.dxf;*.b3p")])
    if file_path:
        global original_dxf_file
        if file_path.endswith('.b3p'):
            with zipfile.ZipFile(file_path, 'r') as zipf:
                zipf.extractall()
                dxf_file = [f for f in zipf.namelist() if f.endswith('.dxf')][0]
                npy_file = [f for f in zipf.namelist() if f.endswith('.npy')][0]
                display_dxf(dxf_file)
                global dots_array
                dots_array = np.load(npy_file)
                os.remove(npy_file)
                original_dxf_file = dxf_file
        else:
            display_dxf(file_path)
            original_dxf_file = file_path
        # set entry 2 text to file path
        entry2.delete(0, tk.END)
        entry2.insert(0, file_path)

def calculate_bounding_box(msp):
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    for entity in msp:
        if entity.dxftype() == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            min_x = min(min_x, start.x, end.x)
            min_y = min(min_y, start.y, end.y)
            max_x = max(max_x, start.x, end.x)
            max_y = max(max_y, start.y, end.y)
        elif entity.dxftype() == 'CIRCLE':
            center = entity.dxf.center
            radius = entity.dxf.radius
            min_x = min(min_x, center.x - radius)
            min_y = min(min_y, center.y - radius)
            max_x = max(max_x, center.x + radius)
            max_y = max(max_y, center.y + radius)
        elif entity.dxftype() == 'SPLINE':
            points = entity.control_points
            for point in points:
                min_x = min(min_x, point[0])
                min_y = min(min_y, point[1])
                max_x = max(max_x, point[0])
                max_y = max(max_y, point[1])
        elif entity.dxftype() == 'INSERT':
            block = entity.block()
            for block_entity in block:
                if block_entity.dxftype() == 'LINE':
                    start = block_entity.dxf.start
                    end = block_entity.dxf.end
                    min_x = min(min_x, start.x, end.x)
                    min_y = min(min_y, start.y, end.y)
                    max_x = max(max_x, start.x, end.x)
                    max_y = max(max_y, start.y, end.y)
                elif block_entity.dxftype() == 'CIRCLE':
                    center = block_entity.dxf.center
                    radius = block_entity.dxf.radius
                    min_x = min(min_x, center.x - radius)
                    min_y = min(min_y, center.y - radius)
                    max_x = max(max_x, center.x + radius)
                    max_y = max(max_y, center.y + radius)
                elif block_entity.dxftype() == 'SPLINE':
                    points = block_entity.control_points
                    for point in points:
                        min_x = min(min_x, point[0])
                        min_y = min(min_y, point[1])
                        max_x = max(max_x, point[0])
                        max_y = max(max_y, point[1])
    return min_x, min_y, max_x, max_y

def display_dxf(file_path):
    try:
        print(f"Reading DXF file: {file_path}")
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        canvas.delete("all")
        
        # Calculate the bounding box of the DXF entities
        min_x, min_y, max_x, max_y = calculate_bounding_box(msp)
        
        # Calculate scale and offset to fit the DXF drawing within the canvas
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        scale_x = canvas_width / (max_x - min_x)
        scale_y = canvas_height / (max_y - min_y)
        scale = min(scale_x, scale_y) * image_scale
        offset_x = -min_x * scale + image_offset_x
        offset_y = -min_y * scale + image_offset_y

        def draw_entity(entity, scale, offset_x, offset_y):
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                canvas.create_line(start.x * scale + offset_x, canvas_height - (start.y * scale + offset_y),
                                   end.x * scale + offset_x, canvas_height - (end.y * scale + offset_y))
                draw_dots_on_line(start, end, scale, offset_x, offset_y)
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius * scale
                canvas.create_oval((center.x - radius) * scale + offset_x, canvas_height - ((center.y - radius) * scale + offset_y),
                                   (center.x + radius) * scale + offset_x, canvas_height - ((center.y + radius) * scale + offset_y))
            elif entity.dxftype() == 'SPLINE':
                points = entity.control_points
                for i in range(len(points) - 1):
                    canvas.create_line(points[i][0] * scale + offset_x, canvas_height - (points[i][1] * scale + offset_y),
                                       points[i + 1][0] * scale + offset_x, canvas_height - (points[i + 1][1] * scale + offset_y))
                    draw_dots_on_line(points[i], points[i + 1], scale, offset_x, offset_y)
            elif entity.dxftype() == 'INSERT':
                block = entity.block()
                for block_entity in block:
                    draw_entity(block_entity, scale, offset_x, offset_y)
            else:
                print(f"Entity type not supported: {entity.dxftype()}")

        def draw_dots_on_line(start, end, scale, offset_x, offset_y):
            start_x, start_y = start[0] * scale + offset_x, canvas_height - (start[1] * scale + offset_y)
            end_x, end_y = end[0] * scale + offset_x, canvas_height - (end[1] * scale + offset_y)
            length = np.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            num_dots = int(length // dot_distance)
            dot_positions = np.linspace(0, 1, num_dots)
            for pos in dot_positions:
                dot_x = start_x + pos * (end_x - start_x)
                dot_y = start_y + pos * (end_y - start_y)
                canvas.create_oval(dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2, fill='red')
                dots.append([dot_x, dot_y])

        global dots
        dots = []
        for entity in msp:
            draw_entity(entity, scale, offset_x, offset_y)

        global dots_array
        dots_array = np.array(dots)
        print(dots_array)

    except Exception as e:
        print(f"Error reading DXF file: {e}")

def update_dot_distance(value):
    slider_label.config(text=f"Dot Distance: {float(value):.2f}")
    global dot_distance
    dot_distance = float(value)
    if entry2.get():
        file_path = entry2.get()
        if file_path.endswith('.b3p'):
            with zipfile.ZipFile(file_path, 'r') as zipf:
                dxf_file = [f for f in zipf.namelist() if f.endswith('.dxf')][0]
                display_dxf(dxf_file)
        else:
            display_dxf(file_path)

def update_image_scale(value):
    scale_label.config(text=f"Image Scale: {float(value):.2f}")
    global image_scale
    image_scale = float(value)
    if entry2.get():
        file_path = entry2.get()
        if file_path.endswith('.b3p'):
            with zipfile.ZipFile(file_path, 'r') as zipf:
                dxf_file = [f for f in zipf.namelist() if f.endswith('.dxf')][0]
                display_dxf(dxf_file)
        else:
            display_dxf(file_path)

def move_image(dx, dy):
    global image_offset_x, image_offset_y
    image_offset_x += dx
    image_offset_y += dy
    if entry2.get():
        file_path = entry2.get()
        if file_path.endswith('.b3p'):
            with zipfile.ZipFile(file_path, 'r') as zipf:
                dxf_file = [f for f in zipf.namelist() if f.endswith('.dxf')][0]
                display_dxf(dxf_file)
        else:
            display_dxf(file_path)

def save_dots():
    save_path = filedialog.asksaveasfilename(defaultextension=".b3p", filetypes=[("B3P files", "*.b3p")])
    if save_path:
        np.save("dots.npy", dots_array)
        with zipfile.ZipFile(save_path, 'w') as zipf:
            zipf.write(original_dxf_file, os.path.basename(original_dxf_file))
            zipf.write("dots.npy")
        os.remove("dots.npy")
        print(f"Saved to {save_path}")

def switch_to_tab1():
    tab_control.select(tab1)

def update_camera_view():
    ret, frame = cap.read()
    if ret:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        camera_label.imgtk = imgtk
        camera_label.configure(image=imgtk)
    camera_label.after(10, update_camera_view)

if __name__ == "__main__":
    root = ThemedTk(theme="arc")
    root.title("Input Printer with Tabs")

    tab_control = ttk.Notebook(root)

    tab1 = ttk.Frame(tab_control)
    tab2 = ttk.Frame(tab_control)
    tab_calibration = ttk.Frame(tab_control)  # New Calibration tab


    tab_control.add(tab1, text='Console Control')
    tab_control.add(tab2, text='Open File Dialog')
    tab_control.add(tab_calibration, text='Calibration')  # Add new tab
    tab_control.pack(expand=1, fill='both')

    # Tab 1
    frame1 = ttk.Frame(tab1)
    frame1.pack(padx=10, pady=10, fill='both', expand=True)

    camera_label = ttk.Label(frame1)
    camera_label.grid(row=0, column=0, columnspan=2, pady=10)

    label_fpga_output = ttk.Label(frame1, text="FPGA Output")
    label_fpga_output.grid(row=1, column=0, columnspan=2, sticky='w', pady=5)

    text_fpga_output = tk.Text(frame1, height=8, width=50)
    text_fpga_output.grid(row=2, column=0, columnspan=2, padx=0, pady=(0, 10), sticky='ew')
    
    label_fpga_command = ttk.Label(frame1, text="FPGA Command")
    label_fpga_command.grid(row=3, column=0, columnspan=2, sticky='w', pady=5)

    text_fpga_command = tk.Text(frame1, height=8, width=50)
    text_fpga_command.grid(row=4, column=0, columnspan=2, padx=0, pady=(0, 10), sticky='ew')

    label_custom_control = ttk.Label(frame1, text="Custom Control")
    label_custom_control.grid(row=5, column=0, columnspan=2, sticky='w', pady=5)

    frame1.grid_columnconfigure(0, weight=1)

    entry1 = ttk.Entry(frame1)
    entry1.grid(row=6, column=0, padx=(0, 20), sticky='ew')

    button1 = ttk.Button(frame1, text="Execute", command=print_input)
    button1.grid(row=6, column=1, sticky='e')
    
    button_start_print = ttk.Button(frame1, text="Start Printing", command=start_print)
    button_start_print.grid(row=7, column=0, columnspan=2, sticky='ew', pady=10)

    # Tab 2
    frame2 = ttk.Frame(tab2)
    frame2.pack(padx=10, pady=10, fill='both', expand=True)

    frame2.grid_columnconfigure(0, weight=1)

    entry2 = ttk.Entry(frame2)
    entry2.grid(row=0, column=0, padx=(0, 10), sticky='ew')

    button2 = ttk.Button(frame2, text="Open File", command=open_file_dialog)
    button2.grid(row=0, column=1, sticky='e')

    slider_label = ttk.Label(frame2, text="Dot Distance: 1.00")
    slider_label.grid(row=1, column=1, sticky='w', pady=5)

    slider = ttk.Scale(frame2, from_=1, to=10, orient=tk.HORIZONTAL, command=update_dot_distance)
    slider.grid(row=1, column=0, padx=(0, 10), sticky='ew')

    scale_label = ttk.Label(frame2, text="Image Scale: 1.00")
    scale_label.grid(row=2, column=1, sticky='w', pady=5)

    scale_slider = ttk.Scale(frame2, from_=0.1, to=5.0, orient=tk.HORIZONTAL, command=update_image_scale)
    scale_slider.set(1.0)
    scale_slider.grid(row=2, column=0, padx=(0, 10), sticky='ew')

    canvas = tk.Canvas(frame2, width=500, height=500, bg="white")
    canvas.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

    joystick_frame = ttk.Frame(frame2)
    joystick_frame.grid(row=4, column=0, columnspan=2, pady=10)

    up_button = ttk.Button(joystick_frame, text="Up", command=lambda: move_image(0, -10))
    up_button.grid(row=0, column=1)

    left_button = ttk.Button(joystick_frame, text="Left", command=lambda: move_image(-10, 0))
    left_button.grid(row=1, column=0)

    down_button = ttk.Button(joystick_frame, text="Down", command=lambda: move_image(0, 10))
    down_button.grid(row=1, column=1)

    right_button = ttk.Button(joystick_frame, text="Right", command=lambda: move_image(10, 0))
    right_button.grid(row=1, column=2)

    save_button = ttk.Button(frame2, text="Save", command=save_dots)
    save_button.grid(row=5, column=0, pady=10, sticky='ew')

    send_button = ttk.Button(frame2, text="Send", command=switch_to_tab1)
    send_button.grid(row=5, column=1, pady=10, sticky='ew')

    # Tab Calibration
    frame_calibration = ttk.Frame(tab_calibration)
    frame_calibration.pack(padx=10, pady=10, fill='both', expand=True)
    
    # Add calibration widgets here
    calibration_label = ttk.Label(frame_calibration, text="Calibration Grid Size")
    calibration_label.grid(row=0, column=0, columnspan=3, pady=5, sticky='w')

    calibration_options = ["3x3", "5x5", "9x9", "17x17"]
    calibration_var = tk.StringVar(value=calibration_options[0])

    calibration_dropdown = ttk.Combobox(frame_calibration, textvariable=calibration_var, values=calibration_options)
    calibration_dropdown.grid(row=0, column=3, columnspan=4, pady=5, sticky='ew')
    
    def create_calibration_grid(size):
        for widget in frame_calibration.grid_slaves():
            if int(widget.grid_info()["row"]) > 0:
                widget.grid_forget()

        grid_size = int(size.split('x')[0])
        for i in range(grid_size):
            for j in range(grid_size):
                entry = ttk.Entry(frame_calibration, width=5)
                entry.grid(row=i + 1, column=j, padx=5, pady=5)

    def on_calibration_option_change(event):
        print
        create_calibration_grid(calibration_var.get())

    calibration_dropdown.bind("<<ComboboxSelected>>", on_calibration_option_change)
    create_calibration_grid(calibration_var.get())

    dot_distance = 1.0
    image_scale = 1.0
    image_offset_x = 0
    image_offset_y = 0
    dots_array = np.array([])
    original_dxf_file = ""

    cap = cv2.VideoCapture(0)
    update_camera_view()

    root.mainloop()

    cap.release()
    cv2.destroyAllWindows()