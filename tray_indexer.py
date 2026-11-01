"""
System Tray File Indexer
Provides a system tray interface for the Smart File Indexer.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import pystray
from PIL import Image, ImageDraw
from pathlib import Path
from file_indexer import FileIndexer
from file_monitor import FileMonitor

class TrayFileIndexer:
    def __init__(self):
        self.indexer = FileIndexer()
        self.icon = None
        self.setup_tray_icon()
        
    def setup_tray_icon(self):
        """Create the system tray icon"""
        # Create a simple icon
        image = self.create_icon()
        
        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Show Suggestions", self.show_suggestions),
            pystray.MenuItem("Add Monitor Directory", self.add_monitor),
            pystray.MenuItem("Settings", self.show_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.stop)
        )
        
        self.icon = pystray.Icon("file_indexer", image, "Smart File Indexer", menu)
        
    def create_icon(self):
        """Create a simple icon for the system tray"""
        # Create a 64x64 image with a simple design
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a simple folder icon
        draw.rectangle([10, 15, 54, 50], fill=(70, 130, 180, 255), outline=(50, 100, 150, 255), width=2)
        draw.rectangle([10, 15, 25, 25], fill=(70, 130, 180, 255), outline=(50, 100, 150, 255), width=2)
        
        # Draw some file icons inside
        draw.rectangle([15, 30, 25, 35], fill=(255, 255, 255, 255))
        draw.rectangle([15, 38, 30, 43], fill=(255, 255, 255, 255))
        draw.rectangle([15, 46, 28, 51], fill=(255, 255, 255, 255))
        
        return image
    
    def show_suggestions(self, icon=None, item=None):
        """Show suggestions in a popup window"""
        if self.indexer.suggestions_queue:
            self.show_suggestions_window()
        else:
            messagebox.showinfo("File Indexer", "No pending suggestions")
    
    def show_suggestions_window(self):
        """Show a window with file suggestions"""
        # Create a simple window for suggestions
        root = tk.Tk()
        root.title("File Organization Suggestions")
        root.geometry("600x400")
        
        # Make it modal
        root.transient()
        root.grab_set()
        
        # Title
        tk.Label(root, text="File Organization Suggestions", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Suggestions list
        frame = tk.Frame(root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create listbox with scrollbar
        listbox = tk.Listbox(frame, height=15)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate suggestions
        for i, suggestion in enumerate(self.indexer.suggestions_queue):
            file_path = Path(suggestion["file_path"])
            category = self.indexer.categorize_file(suggestion["file_path"])
            listbox.insert(tk.END, f"{file_path.name} ({category})")
        
        # Action buttons
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)
        
        def process_selection():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                suggestion = self.indexer.suggestions_queue[index]
                self.show_suggestion_options(suggestion, root)
        
        def skip_all():
            self.indexer.suggestions_queue.clear()
            root.destroy()
            messagebox.showinfo("File Indexer", "All suggestions skipped")
        
        tk.Button(button_frame, text="Process Selected", command=process_selection).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Skip All", command=skip_all).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Close", command=root.destroy).pack(side=tk.LEFT, padx=5)
        
        root.mainloop()
    
    def show_suggestion_options(self, suggestion, parent_window):
        """Show options for a specific suggestion"""
        options_window = tk.Toplevel(parent_window)
        options_window.title("File Organization Options")
        options_window.geometry("500x300")
        options_window.transient(parent_window)
        options_window.grab_set()
        
        file_path = Path(suggestion["file_path"])
        
        # File info
        tk.Label(options_window, text=f"File: {file_path.name}", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(options_window, text=f"Location: {file_path.parent}").pack(pady=5)
        
        # Options list
        options_frame = tk.Frame(options_window)
        options_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        options_listbox = tk.Listbox(options_frame, height=10)
        options_scrollbar = tk.Scrollbar(options_frame, orient=tk.VERTICAL, command=options_listbox.yview)
        options_listbox.configure(yscrollcommand=options_scrollbar.set)
        
        options_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        options_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate options
        for option in suggestion["suggestions"]:
            if option["action"] == "move":
                display_text = f"Move to: {Path(option['destination']).parent}"
            else:
                display_text = "Keep in current location"
            if option.get("learned_count"):
                display_text += f"  (your usual, {option['learned_count']} times)"
            options_listbox.insert(tk.END, display_text)
        
        # Action buttons
        def execute_option():
            selection = options_listbox.curselection()
            if selection:
                selected_option = suggestion["suggestions"][selection[0]]
                if self.indexer.execute_suggestion(selected_option, selected_option["action"]):
                    # Remove from queue
                    self.indexer.suggestions_queue.remove(suggestion)
                    options_window.destroy()
                    messagebox.showinfo("Success", "File organized successfully!")
                else:
                    messagebox.showerror("Error", self.indexer.last_error or "Failed to organize file")
        
        def skip_file():
            self.indexer.suggestions_queue.remove(suggestion)
            options_window.destroy()
        
        button_frame = tk.Frame(options_window)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Execute", command=execute_option).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Skip", command=skip_file).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=options_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def add_monitor(self, icon=None, item=None):
        """Add a directory to monitoring"""
        # Create a simple dialog for directory selection
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        from tkinter import filedialog
        directory = filedialog.askdirectory(title="Select directory to monitor")
        
        if directory:
            if self.indexer.add_monitored_directory(directory):
                messagebox.showinfo("Success", f"Added {directory} to monitoring")
            else:
                messagebox.showerror("Error", f"Failed to add {directory} to monitoring")
        
        root.destroy()
    
    def show_settings(self, icon=None, item=None):
        """Show settings dialog"""
        root = tk.Tk()
        root.title("File Indexer Settings")
        root.geometry("400x300")
        
        # Settings content
        tk.Label(root, text="File Indexer Settings", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Auto-sort setting
        auto_sort_var = tk.BooleanVar(value=self.indexer.config.getboolean('DEFAULT', 'auto_sort', fallback=True))
        tk.Checkbutton(root, text="Auto-sort files", variable=auto_sort_var).pack(pady=5)
        
        # Notification delay
        tk.Label(root, text="Notification delay (seconds):").pack(pady=5)
        delay_var = tk.StringVar(value=self.indexer.config.get('DEFAULT', 'notification_delay', fallback='30'))
        tk.Entry(root, textvariable=delay_var).pack(pady=5)
        
        # Monitored directories
        tk.Label(root, text="Monitored Directories:", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        
        monitored_listbox = tk.Listbox(root, height=6)
        monitored_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Populate monitored directories
        monitored_dirs = self.indexer.file_monitor.get_monitored_directories()
        for directory in monitored_dirs:
            monitored_listbox.insert(tk.END, directory)
        
        # Remove directory button
        def remove_directory():
            selection = monitored_listbox.curselection()
            if selection:
                directory = monitored_listbox.get(selection[0])
                if self.indexer.remove_monitored_directory(directory):
                    monitored_listbox.delete(selection[0])
                    messagebox.showinfo("Success", f"Removed {directory} from monitoring")
                else:
                    messagebox.showerror("Error", f"Failed to remove {directory} from monitoring")
        
        tk.Button(root, text="Remove Selected Directory", command=remove_directory).pack(pady=5)
        
        # Save button
        def save_settings():
            self.indexer.config['DEFAULT']['auto_sort'] = str(auto_sort_var.get())
            self.indexer.config['DEFAULT']['notification_delay'] = delay_var.get()
            self.indexer.save_config()
            root.destroy()
            messagebox.showinfo("Settings", "Settings saved successfully!")
        
        tk.Button(root, text="Save", command=save_settings).pack(pady=20)
        
        root.mainloop()
    
    def check_suggestions_periodic(self):
        """Periodically check for suggestions and show notifications"""
        if self.indexer.suggestions_queue:
            # Show notification
            self.icon.notify(
                title="File Organization Suggestions",
                message=f"You have {len(self.indexer.suggestions_queue)} file(s) to organize"
            )
        
        # Schedule next check
        threading.Timer(30.0, self.check_suggestions_periodic).start()
    
    def run(self):
        """Start the system tray application"""
        if self.indexer.rules_error:  # pythonw has no console, so say it in a window
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("Rules not loaded", self.indexer.rules_warning())
            root.destroy()

        # Start monitoring
        self.indexer.start_monitoring()
        
        # Start periodic checking
        self.check_suggestions_periodic()
        
        # Run the system tray icon
        self.icon.run()
    
    def stop(self, icon=None, item=None):
        """Stop the application"""
        self.indexer.stop_monitoring()
        self.icon.stop()

if __name__ == "__main__":
    app = TrayFileIndexer()
    app.run() 