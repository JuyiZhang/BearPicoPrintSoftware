import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import ezdxf
import numpy as np
import zipfile
import os
import cv2
import atexit
import sys
import signal
from PIL import Image, ImageTk

import platform
from numerical.util import printer   # <-- add printer import

if platform.system() != "Darwin":
    from ttkthemes import ThemedTk
else:
    from tkinter import Tk as ThemedTk

# Global printer instance with default configuration
printer_instance = printer(15, 10)   # default values
print_command = ""
calibration_voltages = []

def start_print():
    print("Starting print...")
    printer_instance.executeCommand()

def print_input():
    user_input = entry1.get()
    print(user_input)

def exit_handler():
    printer_instance.__deinit__()
    print("Cleaning up")
    sys.exit(0)

def kill_handler(*args):
    printer_instance.__deinit__()
    sys.exit(0)

atexit.register(exit_handler)
signal.signal(signal.SIGINT, kill_handler)
signal.signal(signal.SIGTERM, kill_handler)

def open_file_dialog():
    # if using mac
    if platform.system() == "Darwin":
        file_path = filedialog.askopenfilename()
    else:
        file_path = filedialog.askopenfilename(filetypes=[("DXF, PNG and B3P files", "*.dxf;*.png;*.b3p")])
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
        elif file_path.lower().endswith('.png'):
            display_png(file_path)
            original_dxf_file = file_path
        else:
            display_dxf(file_path)
            original_dxf_file = file_path
        # set entry2 text to file path
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
        # get width and height of the array
        width = dots_array[:, 0].max() - dots_array[:, 0].min()
        height = dots_array[:, 1].max() - dots_array[:, 1].min()
        print(f"Width: {width}, Height: {height}. Dots: {len(dots_array)}")
        

    except Exception as e:
        print(f"Error reading DXF file: {e}")

def display_png(file_path):
    try:
        print(f"Reading PNG file: {file_path}")
        img = Image.open(file_path)
        canvas.delete("all")
        
        # Get canvas dimensions
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        img_width, img_height = img.size
        
        # Scale image to fit canvas while preserving aspect ratio and applying image_scale
        scale_factor = min(canvas_width / img_width, canvas_height / img_height) * image_scale
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        resized_img = img.resize((new_width, new_height))
        photo = ImageTk.PhotoImage(resized_img)
        
        # Center image on canvas and apply global offsets
        x_center = canvas_width / 2 + image_offset_x
        y_center = canvas_height / 2 + image_offset_y
        canvas.create_image(x_center, y_center, image=photo, anchor='center')
        canvas.photo = photo  # prevent garbage collection
        
        # Calculate top-left corner coordinates of the displayed image
        top_left_x = x_center - new_width / 2
        top_left_y = y_center - new_height / 2
        
        # Overlay dots in a grid across the image area
        global dots
        dots = []
        # Use dot_distance as the grid spacing (ensure a minimum step of 1 pixel)
        step = int(dot_distance) if dot_distance >= 1 else 1
        for x in range(0, new_width, step):
            for y in range(0, new_height, step):
                # get the pixel data from the image
                pixel = resized_img.getpixel((x, y))
                print(f"Pixel at ({x}, {y}): {pixel}")
                # check if the pixel is not white
                if pixel[3] != 0:
                    # draw a dot on the canvas
                    dot_x = top_left_x + x
                    dot_y = top_left_y + y
                    canvas.create_oval(dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2, fill='red')
                    dots.append([dot_x, dot_y])
        
        global dots_array
        dots_array = np.array(dots)
        if len(dots_array) > 0:
            grid_width = dots_array[:, 0].max() - dots_array[:, 0].min()
            grid_height = dots_array[:, 1].max() - dots_array[:, 1].min()
        else:
            grid_width = grid_height = 0
        print(f"PNG image displayed with grid dots. Grid width: {grid_width}, height: {grid_height}. Total dots: {len(dots)}")
    except Exception as e:
        print(f"Error reading PNG file: {e}")

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
        elif file_path.lower().endswith('.png'):
            display_png(file_path)
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
        elif file_path.lower().endswith('.png'):
            display_png(file_path)
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
        elif file_path.lower().endswith('.png'):
            display_png(file_path)
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
    global dots_array
    printer_instance.clearCommand()
    text_fpga_command.delete(1.0, tk.END)
    
    if dots_array is not None:
        for dot in dots_array:
            if printer_instance.calibrationType == 'C' or printer_instance.calibrationType == 'B':
                Ux, Uy, Ua, Ub, Uc, Ud, result = printer_instance.toUCoordCalibrated(dot[0]/100, dot[1]/100) # coordinate is set to be 5mmx5mm, need actual data to check
                if result != 1:
                    printer_instance.addCommand(Ua, Ub, Uc, Ud)
                    print_cmd_single_line = f"DISP NORM {Ua} {Ub} {Uc} {Ud}"
                    text_fpga_command.insert(tk.END, print_cmd_single_line + "\n")
                    continue
                    
            Ua = dot[0]*10 - 2500
            Uc = 0
            if Ua < 0:
                Ua = 0
                Uc = 2500 - dot[0]*10
            Ub = dot[1]*10 - 2500
            Ud = 0
            if Ub < 0:
                Ub = 0
                Ud = 2500 - dot[1]*10
            printer_instance.addCommand(Ua, Ub, Uc, Ud)
            print_cmd_single_line = f"DISP NORM {Ua} {Ub} {Uc} {Ud}"
            text_fpga_command.insert(tk.END, print_cmd_single_line + "\n")

def generate_pattern_to_print():
    print("Generating pattern to print...")
    printer_instance.clearCommand()
    text_fpga_command.delete(1.0, tk.END)

    # Get the selected grid size
    grid_size = int(calibration_var.get()[0])
    print(f"Selected grid size: {grid_size}")
    
    grid_distance = float(calibration_pattern_distance_entry.get())
    print(f"Pattern distance: {grid_distance}")
    
    global proceed_without_error
    proceed_without_error = True
    for i in range(grid_size):
        for j in range(grid_size):
            print(proceed_without_error)
            voltages = printer_instance.toU((i-(grid_size-1)/2)*grid_distance/1000, (j-(grid_size-1)/2)*grid_distance/1000)
            if voltages[6] == -1 and proceed_without_error:
                    
                alert = tk.Toplevel(root)
                alert.title("Invalid Voltage")

                tk.Label(alert, text="Invalid voltage detected. Do you want to Abort?").pack(padx=20, pady=20)

                def proceed():
                    global proceed_without_error
                    proceed_without_error = False
                    alert.destroy()

                def cancel():
                    alert.destroy()
                    text_fpga_command.delete(1.0, tk.END)
                    return

                ttk.Button(alert, text="Proceed", command=proceed).pack(side=tk.LEFT, padx=10, pady=10)
                ttk.Button(alert, text="Abort", command=cancel).pack(side=tk.RIGHT, padx=10, pady=10)

                alert.transient(root)
                alert.grab_set()
                root.wait_window(alert)
            
            printer_instance.addCommand(voltages[2], voltages[3], voltages[4], voltages[5])
            calibration_voltages.append([voltages[0],voltages[1]])
            print_cmd_single_line = f"DISP NORM {voltages[2]} {voltages[3]} {voltages[4]} {voltages[5]}"
            text_fpga_command.insert(tk.END, print_cmd_single_line + "\n")
    
    tab_control.select(tab1)  # Switch to tab 1 after generating the pattern

    # Generate the calibration pattern

def update_camera_view():
    ret, frame = cap.read()
    if ret:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        camera_label.imgtk = imgtk
        camera_label.configure(image=imgtk)
    camera_label.after(10, update_camera_view)

def select_firmware():
    # Open file dialog to select firmware
    firmware_path = filedialog.askopenfilename(filetypes=[("Firmware files", "*.lvbitx")])
    if firmware_path:
        # Update the printer instance with the selected firmware
        global printer_instance
        printer_instance.updateFirmware(firmware_path)
        print(f"Firmware updated to {firmware_path}")
        return 0
    else:
        print("No firmware selected")
        return 1

def printer_print_line():
    # add a popup window to select line type, line length, and line axis
    line_window = tk.Toplevel(root)
    line_window.title("Line Configuration")
    # add dropdown to select line axis (A, B, C, D)
    line_axis_label = ttk.Label(line_window, text="Line Axis:")
    line_axis_label.grid(row=0, column=0, padx=10, pady=10)
    line_axis_var = tk.StringVar(value="A")
    line_axis_dropdown = ttk.Combobox(line_window, textvariable=line_axis_var, values=["A", "B", "C", "D"])
    line_axis_dropdown.grid(row=0, column=1, columnspan=2, padx=10, pady=10)
    # add two horizontal entrys for line minimum and maximum
    line_min_label = ttk.Label(line_window, text="Line Min:")
    line_min_label.grid(row=1, column=0, padx=10, pady=10)
    line_min_entry = ttk.Entry(line_window)
    line_min_entry.grid(row=2, column=0, padx=10, pady=10)
    line_step_label = ttk.Label(line_window, text="Line Step:")
    line_step_label.grid(row=1, column=1, padx=10, pady=10)
    line_step_entry = ttk.Entry(line_window)
    line_step_entry.grid(row=2, column=1, padx=10, pady=10)
    line_max_label = ttk.Label(line_window, text="Line Max:")
    line_max_label.grid(row=1, column=2, padx=10, pady=10)
    line_max_entry = ttk.Entry(line_window)
    line_max_entry.grid(row=2, column=2, padx=10, pady=10)
    # add a button to execute the line command
    def execute_line_command():
        printer_instance.clearCommand()
        text_fpga_command.delete(1.0, tk.END)
        line_axis = line_axis_var.get()
        line_min = float(line_min_entry.get())
        line_max = float(line_max_entry.get())
        line_step = float(line_step_entry.get())
        for i in range(int((line_max-line_min)/line_step)):
            if line_axis == "A":
                printer_instance.addCommand(i*line_step+line_min, 0, 0, 0)
                print_cmd_single_line = f"DISP NORM {i*line_step+line_min} 0 0 0"
            elif line_axis == "B":
                printer_instance.addCommand(0, i*line_step+line_min, 0, 0)
                print_cmd_single_line = f"DISP NORM 0 {i*line_step+line_min} 0 0"
            elif line_axis == "C":
                printer_instance.addCommand(0, 0, i*line_step+line_min, 0)
                print_cmd_single_line = f"DISP NORM 0 0 {i*line_step+line_min} 0"
            elif line_axis == "D":
                printer_instance.addCommand(0, 0, 0, i*line_step+line_min)
                print_cmd_single_line = f"DISP NORM 0 0 0 {i*line_step+line_min}"
            text_fpga_command.insert(tk.END, print_cmd_single_line + "\n")
        
        tab_control.select(tab1)
        print(printer_instance.command)
        line_window.destroy()
        
    execute_button = ttk.Button(line_window, text="Execute", command=execute_line_command)
    execute_button.grid(row=3, column=0, columnspan=3, padx=10, pady=10)
    
    

def printer_print_oval():
    # add a popup window to select oval width, oval height, dot distance
    oval_window = tk.Toplevel(root)
    oval_window.title("Oval Configuration")
    oval_axis_label = ttk.Label(oval_window, text="Oval Axis:")
    oval_axis_label.grid(row=0, column=0, padx=10, pady=10)
    oval_axis_var = tk.StringVar(value="A-B")
    oval_axis_dropdown = ttk.Combobox(oval_window, textvariable=oval_axis_var, values=["A-B", "A-D", "C-B", "C-D"])
    oval_axis_dropdown.grid(row=0, column=1, columnspan=2, padx=10, pady=10)
    hline_min_label = ttk.Label(oval_window, text="HAxis Length:")
    hline_min_label.grid(row=1, column=0, padx=10, pady=10)
    hline_min_entry = ttk.Entry(oval_window)
    hline_min_entry.grid(row=2, column=0, padx=10, pady=10)
    vaxis_length_label = ttk.Label(oval_window, text="VAxis Length:")
    vaxis_length_label.grid(row=1, column=1, padx=10, pady=10)
    vaxis_length_entry = ttk.Entry(oval_window)
    vaxis_length_entry.grid(row=2, column=1, padx=10, pady=10)
    x_pos_label = ttk.Label(oval_window, text="X Pos:")
    x_pos_label.grid(row=3, column=0, padx=10, pady=10)
    x_pos_entry = ttk.Entry(oval_window)
    x_pos_entry.grid(row=4, column=0, padx=10, pady=10)
    y_pos_label = ttk.Label(oval_window, text="Y Pos:")
    y_pos_label.grid(row=3, column=1, padx=10, pady=10)
    y_pos_entry = ttk.Entry(oval_window)
    y_pos_entry.grid(row=4, column=1, padx=10, pady=10)
    step_label = ttk.Label(oval_window, text="Step:")
    step_label.grid(row=5, column=0, padx=10, pady=10)
    step_entry = ttk.Entry(oval_window)
    step_entry.grid(row=5, column=1, padx=10, pady=10)
    
    # add a button to execute the oval command
    def execute_oval_command():
        printer_instance.clearCommand()
        text_fpga_command.delete(1.0, tk.END)
        haxis_length = float(hline_min_entry.get())
        vaxis_length = float(vaxis_length_entry.get())
        x_pos = float(x_pos_entry.get())
        y_pos = float(y_pos_entry.get())
        step = float(step_entry.get())
        axis = oval_axis_var.get()
        for i in range(int(360/step)):
            if oval_axis_var.get() == "A-B":
                printer_instance.addCommand(x_pos + haxis_length*np.cos(np.radians(i)), y_pos + vaxis_length*np.sin(np.radians(i)), 0, 0)
                print_cmd_single_line = f"DISP NORM {x_pos + haxis_length*np.cos(np.radians(i))} {y_pos + vaxis_length*np.sin(np.radians(i))} 0 0"
            elif oval_axis_var.get() == "A-D":
                printer_instance.addCommand(x_pos + haxis_length*np.cos(np.radians(i)), 0, 0, y_pos + vaxis_length*np.sin(np.radians(i)))
                print_cmd_single_line = f"DISP NORM {x_pos + haxis_length*np.cos(np.radians(i))} 0 0 {y_pos + vaxis_length*np.sin(np.radians(i))}"
            elif oval_axis_var.get() == "C-B":
                printer_instance.addCommand(0, x_pos + haxis_length*np.cos(np.radians(i)), y_pos + vaxis_length*np.sin(np.radians(i)), 0)
                print_cmd_single_line = f"DISP NORM 0 {x_pos + haxis_length*np.cos(np.radians(i))} {y_pos + vaxis_length*np.sin(np.radians(i))} 0"
            elif oval_axis_var.get() == "C-D":
                printer_instance.addCommand(0, 0, x_pos + haxis_length*np.cos(np.radians(i)), y_pos + vaxis_length*np.sin(np.radians(i)))
                print_cmd_single_line = f"DISP NORM 0 0 {x_pos + haxis_length*np.cos(np.radians(i))} {y_pos + vaxis_length*np.sin(np.radians(i))}"
            text_fpga_command.insert(tk.END, print_cmd_single_line + "\n")
        tab_control.select(tab1)
        print(printer_instance.command)
        oval_window.destroy()
    # add a button to execute the oval command
    execute_cmd_button = ttk.Button(oval_window, text="Execute", command=execute_oval_command)
    execute_cmd_button.grid(row=6, column=0, columnspan=2, padx=10, pady=10)
    print("printing oval")
        
    

    
def printer_print_square():
    # add a popup window to select square width, square height, dot distance
    square_window = tk.Toplevel(root)
    square_window.title("Square Configuration")
    # add two horizontal entrys for square width and height
    hline_axis_label = ttk.Label(square_window, text="H/VLine Axis:")
    hline_axis_label.grid(row=0, column=0, padx=10, pady=10)
    hline_axis_var = tk.StringVar(value="A-B")
    hline_axis_dropdown = ttk.Combobox(square_window, textvariable=hline_axis_label, values=["A-B", "A-D", "C-B", "C-D"])
    hline_axis_dropdown.grid(row=0, column=1, columnspan=2, padx=10, pady=10)
    hline_min_label = ttk.Label(square_window, text="HLine Min:")
    hline_min_label.grid(row=1, column=0, padx=10, pady=10)
    hline_min_entry = ttk.Entry(square_window)
    hline_min_entry.grid(row=2, column=0, padx=10, pady=10)
    hline_step_label = ttk.Label(square_window, text="HLine Step:")
    hline_step_label.grid(row=1, column=1, padx=10, pady=10)
    hline_step_entry = ttk.Entry(square_window)
    hline_step_entry.grid(row=2, column=1, padx=10, pady=10)
    hline_max_label = ttk.Label(square_window, text="HLine Max:")
    hline_max_label.grid(row=1, column=2, padx=10, pady=10)
    hline_max_entry = ttk.Entry(square_window)
    hline_max_entry.grid(row=2, column=2, padx=10, pady=10)
    vline_min_label = ttk.Label(square_window, text="VLine Min:")
    vline_min_label.grid(row=3, column=0, padx=10, pady=10)
    vline_min_entry = ttk.Entry(square_window)
    vline_min_entry.grid(row=4, column=0, padx=10, pady=10)
    vline_step_label = ttk.Label(square_window, text="VLine Step:")
    vline_step_label.grid(row=3, column=1, padx=10, pady=10)
    vline_step_entry = ttk.Entry(square_window)
    vline_step_entry.grid(row=4, column=1, padx=10, pady=10)
    vline_max_label = ttk.Label(square_window, text="VLine Max:")
    vline_max_label.grid(row=3, column=2, padx=10, pady=10)
    vline_max_entry = ttk.Entry(square_window)
    vline_max_entry.grid(row=4, column=2, padx=10, pady=10)
    # add a button to execute the square command
    def execute_square_command():
        printer_instance.clearCommand()
        text_fpga_command.delete(1.0, tk.END)
        hmin = float(hline_min_entry.get())
        hstep = float(hline_step_entry.get())
        hmax = float(hline_max_entry.get())
        vmin = float(vline_min_entry.get())
        vstep = float(vline_step_entry.get())
        vmax = float(vline_max_entry.get())
        axis = hline_axis_var.get()
        for i in range(int((hmax-hmin)/hstep)):
            for j in range(int((vmax-vmin)/vstep)):
                if hline_axis_var.get() == "A-B":
                    printer_instance.addCommand(i*hstep+hmin, j*vstep+vmin, 0, 0)
                    print_cmd_single_line = f"DISP NORM {i*hstep+hmin} {j*vstep+vmin} 0 0"
                elif hline_axis_var.get() == "A-D":
                    printer_instance.addCommand(i*hstep+hmin, 0, 0, j*vstep+vmin)
                    print_cmd_single_line = f"DISP NORM {i*hstep+hmin} 0 0 {j*vstep+vmin}"
                elif hline_axis_var.get() == "C-B":
                    printer_instance.addCommand(0, i*hstep+hmin, j*vstep+vmin, 0)
                    print_cmd_single_line = f"DISP NORM 0 {i*hstep+hmin} {j*vstep+vmin} 0"
                elif hline_axis_var.get() == "C-D":
                    printer_instance.addCommand(0, 0, i*hstep+hmin, j*vstep+vmin)
                    print_cmd_single_line = f"DISP NORM 0 0 {i*hstep+hmin} {j*vstep+vmin}"
                text_fpga_command.insert(tk.END, print_cmd_single_line + "\n")
        tab_control.select(tab1)
        print(printer_instance.command)
        square_window.destroy()
    # add a button to execute the oval command
    execute_cmd_button = ttk.Button(square_window, text="Execute", command=execute_square_command)
    execute_cmd_button.grid(row=5, column=0, columnspan=3, padx=10, pady=10)    
    print("printing square")
 

def open_printer_config():
    config = tk.Toplevel(root)
    config.title("Printer Configuration")

    tk.Label(config, text="H: ").grid(row=0, column=0, padx=10, pady=10)
    entry_H = ttk.Entry(config)
    entry_H.grid(row=0, column=1, padx=10, pady=10)

    tk.Label(config, text="d: ").grid(row=1, column=0, padx=10, pady=10)
    entry_d = ttk.Entry(config)
    entry_d.grid(row=1, column=1, padx=10, pady=10)

    tk.Label(config, text="K: ").grid(row=2, column=0, padx=10, pady=10)
    entry_K = ttk.Entry(config)
    entry_K.grid(row=2, column=1, padx=10, pady=10)

    tk.Label(config, text="Uz: ").grid(row=3, column=0, padx=10, pady=10)
    entry_Uz = ttk.Entry(config)
    entry_Uz.grid(row=3, column=1, padx=10, pady=10)

    # Populate entries with current configuration
    entry_H.insert(0, printer_instance.H)
    entry_d.insert(0, printer_instance.d)
    entry_K.insert(0, printer_instance.K)
    entry_Uz.insert(0, printer_instance.Uz)

    def apply_config():
        try:
            H_val = float(entry_H.get())
            d_val = float(entry_d.get())
            K_val = float(entry_K.get())
            Uz_val = float(entry_Uz.get())
            global printer_instance
            printer_instance.updateValues(H_val, d_val, K_val, Uz_val)
            print(f"Printer configured: H={H_val}, d={d_val}, K={K_val}, Uz={Uz_val}")
            update_printer_config_display()
            config.destroy()
        except Exception as e:
            print("Invalid values:", e)

    # Adjust row index for the Apply button
    apply_button = ttk.Button(config, text="Apply", command=apply_config)
    apply_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

def open_print_config():
    config = tk.Toplevel(root)
    config.title("Print Configuration")
    
    tk.Label(config, text="Print Speed (Droplet/s):").grid(row=0, column=0, padx=10, pady=10)
    entry_speed = ttk.Entry(config)
    entry_speed.grid(row=1, column=0, padx=10, pady=10)
    
    entry_speed.insert(0, str(1/printer_instance.dispenseInterval))
    
    tk.Label(config, text="Voltage Threshold (Ratio):").grid(row=2, column=0, padx=10, pady=10)
    entry_voltage = ttk.Entry(config)
    entry_voltage.grid(row=3, column=0, padx=10, pady=10)
    
    entry_voltage.insert(0, str(printer_instance.vthreshold))
    
    def apply_print_config():
        try:
            speed_val = float(entry_speed.get())
            voltage_val = float(entry_voltage.get())
            global printer_instance
            printer_instance.dispenseInterval = 1/speed_val
            printer_instance.vthreshold = voltage_val
            print(f"Print configured: Dispense Interval={printer_instance.dispenseInterval}, Voltage Threshold={printer_instance.vthreshold}")
            config.destroy()
        except Exception as e:
            print("Invalid values:", e)
        
    apply_button = ttk.Button(config, text="Apply", command=apply_print_config)
    apply_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

def open_connect():
    conn_window = tk.Toplevel(root)
    conn_window.title("Connect to Printer")

    tk.Label(conn_window, text="Printer Address:").grid(row=0, column=0, padx=10, pady=10)
    address_entry = ttk.Entry(conn_window)
    address_entry.grid(row=0, column=1, padx=10, pady=10)
    address_entry.insert(0, printer_instance.address)

    def apply_address():
        new_address = address_entry.get()
        printer_instance.updateAddress(new_address)
        print(f"Printer address updated to {new_address}")
        conn_window.destroy()

    apply_button = ttk.Button(conn_window, text="Apply", command=apply_address)
    apply_button.grid(row=1, column=0, columnspan=2, padx=10, pady=10)

def open_calibration_setting():
    tab_control.select(tab_calibration)
    print("Switched to Calibration tab.")

if __name__ == "__main__":
    
    if platform.system() != "Darwin":
        root = ThemedTk(theme="arc")
    else:
        root = tk.Tk()
    root.title("Input Printer with Tabs")

    # --- Add menubar with Printer Configuration and Connect ---
    menubar = tk.Menu(root)
    config_menu = tk.Menu(menubar, tearoff=0)
    config_menu.add_command(label="Config", command=open_printer_config)
    config_menu.add_command(label="Select Firmware", command=select_firmware)
    config_menu.add_command(label="Update Address", command=open_connect)
    menubar.add_cascade(label="Printer", menu=config_menu)

    connect_menu = tk.Menu(menubar, tearoff=0)
    connect_menu.add_command(label="Pre-Calibrate", command=save_dots, state="disabled")
    connect_menu.add_command(label="Line", command=printer_print_line)
    connect_menu.add_command(label="Oval", command=printer_print_oval)
    connect_menu.add_command(label="Rectangle", command=printer_print_square)
    menubar.add_cascade(label="Generate", menu=connect_menu)
    
    print_menu = tk.Menu(menubar, tearoff=0)
    print_menu.add_command(label="Start", command=start_print)
    print_menu.add_command(label="Print Config", command=open_print_config)
    print_menu.add_command(label="Calibration Setting", command=open_calibration_setting)
    menubar.add_cascade(label="Print", menu=print_menu)
    

    root.config(menu=menubar)
    # ------------------------

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

    label_fpga_output = ttk.Label(frame1, text="Real-time View")
    label_fpga_output.grid(row=0, column=0, sticky='w', pady=5)

    camera_label = ttk.Label(frame1)
    camera_label.grid(row=1, column=0, rowspan=3, pady=10, padx=10)

    label_fpga_output = ttk.Label(frame1, text="FPGA Output")
    label_fpga_output.grid(row=0, column=1, sticky='nsew', pady=5)

    text_fpga_output = tk.Text(frame1, height=8, width=50)
    text_fpga_output.grid(row=1, column=1, columnspan=2, padx=0, pady=(0, 10), sticky='nsew')

    
    label_fpga_command = ttk.Label(frame1, text="FPGA Command")
    label_fpga_command.grid(row=2, column=1, columnspan=2, sticky='w', pady=5)

    text_fpga_command = tk.Text(frame1, height=8, width=50)
    text_fpga_command.grid(row=3, column=1, columnspan=2, padx=0, pady=(0, 10), sticky='nsew')

    label_custom_control = ttk.Label(frame1, text="Custom Control")
    label_custom_control.grid(row=4, column=1, sticky='w', pady=5)

    frame1.grid_columnconfigure(0, weight=1)

    entry1 = ttk.Entry(frame1)
    entry1.grid(row=5, column=1, padx=(0, 20), sticky='ew')

    button1 = ttk.Button(frame1, text="Execute", command=print_input)
    button1.grid(row=5, column=2, sticky='e')
    
    button_start_print = ttk.Button(frame1, text="Start Printing", command=start_print)
    button_start_print.grid(row=4, column=0, rowspan=2, sticky='nsew', pady=0, padx=10)

    # --- Inline Printer Configuration Display in Tab 1 ---
    printer_config_panel = ttk.LabelFrame(frame1, text="Current Printer Configuration")
    printer_config_panel.grid(row=6, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
    
    printer_config_button = ttk.Button(frame1, text="Printer Config", command=open_printer_config)
    printer_config_button.grid(row=6, column=2, padx=10, pady=10)

    printer_config_value = tk.StringVar()
    def update_printer_config_display():
        printer_config_value.set(f"H: {printer_instance.H*1000}mm, d: {printer_instance.d*1000}mm, K: {printer_instance.K}, Uz: {printer_instance.Uz/1000}kV")

    update_printer_config_display()  # initial update

    config_display_label = ttk.Label(printer_config_panel, textvariable=printer_config_value)
    config_display_label.grid(row=0, column=0, padx=10, pady=10)
    
    progress_bar = ttk.Progressbar(frame1)
    progress_bar.grid(row=7, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
    # set progress bar to waiting

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
    
    im_scale_label = ttk.Label(frame2, text="Image Scale: 1px:10V")
    im_scale_label.grid(row=6, column=1, sticky='w', pady=5)

    # Tab Calibration
    frame_calibration = ttk.Frame(tab_calibration)
    frame_calibration.pack(padx=10, pady=10, fill='both', expand=True)
    
    calibration_type_label = ttk.Label(frame_calibration, text="Calibration Type:")
    calibration_type_label.grid(row=0, column=0, pady=5, sticky='w')

    calibration_type_var = tk.StringVar(value="None")
    calibration_type_dropdown = ttk.Combobox(frame_calibration, textvariable=calibration_type_var,
                                            values=["None", "Voltage", "Coordinate", "Both"])
    calibration_type_dropdown.grid(row=0, column=1, pady=5, sticky='ew', columnspan=2)

    def on_calibration_type_change(event):
        selection = calibration_type_var.get()
        mapping = {
            "None": "N",
            "Voltage": "V",
            "Coordinate": "C",
            "Both": "B"
        }
        printer_instance.setEnableCalibration(mapping.get(selection, "N"))
        print(f"Calibration type set to: {selection}")

    calibration_type_dropdown.bind("<<ComboboxSelected>>", on_calibration_type_change)
    
    # Add calibration widgets here
    calibration_label = ttk.Label(frame_calibration, text="Calibration Grid Size   ")
    calibration_label.grid(row=1, column=0, pady=5, sticky='w')
    
    #add spacing between widgets
    ttk.Label(frame_calibration, text="  ").grid(row=1, column=1)
    
    generate_pattern_button = ttk.Button(frame_calibration, text="Send to Printer", command=generate_pattern_to_print)
    generate_pattern_button.grid(row=1, column=2, pady=5, sticky='e')
    
    

    calibration_options = ["3x3", "5x5", "9x9", "17x17"]
    calibration_var = tk.StringVar(value=calibration_options[0])

    calibration_dropdown = ttk.Combobox(frame_calibration, textvariable=calibration_var, values=calibration_options)
    calibration_dropdown.grid(row=2, column=0, columnspan=3, pady=5, sticky='ew')
    
    calibration_pattern_distance_label = ttk.Label(frame_calibration, text="Pattern Distance (mm)")
    calibration_pattern_distance_label.grid(row=3, column=0, columnspan=2, pady=5, sticky='w')
    
    calibration_pattern_distance_entry = ttk.Entry(frame_calibration)
    calibration_pattern_distance_entry.grid(row=3, column=2, pady=5, sticky='ew')
    calibration_pattern_distance_entry.insert(0, "10")
    
    frame_calibration_input = ttk.Frame(frame_calibration)
    frame_calibration_input.grid(row=4, column=0, columnspan=3, pady=5, sticky='w')
    
    def save_calibration():
        calibration_data = []
        for row in calibration_entries:
            for entry in row:
                calibration_data.append(entry.get())
        printer_instance.saveCalibrationData(calibration_data, calibration_voltages)
        # You can save calibration_data to a file or process it as needed
    
    save_calibration_button = ttk.Button(frame_calibration, text="Save Calibration", command=save_calibration)
    save_calibration_button.grid(row=5, column=0, columnspan=3, pady=5, sticky='ew')
    
    
    def create_calibration_grid(size):
        for widget in frame_calibration_input.grid_slaves():
            if int(widget.grid_info()["row"]) > 0:
                widget.grid_forget()

        global calibration_entries
        calibration_entries = []
        grid_size = int(size.split('x')[0])
        for i in range(grid_size):
            row_entries = []
            for j in range(grid_size):
                entry = ttk.Entry(frame_calibration_input, width=5)
                entry.grid(row=i, column=j, padx=5, pady=5)
                row_entries.append(entry)
            calibration_entries.append(row_entries)

    

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

    if platform.system() != "Darwin":
        cap = cv2.VideoCapture(0)
        update_camera_view()

    root.mainloop()

    if platform.system() != "Darwin":
        cap.release()
        cv2.destroyAllWindows()