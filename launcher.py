#!/usr/bin/env python3
"""
Smart File Indexer Launcher
Choose between GUI mode and System Tray mode
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os

class LauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Smart File Indexer Launcher")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        # Center the window
        self.center_window()
        
        self.setup_ui()
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Smart File Indexer", font=("Arial", 18, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Description
        desc_label = ttk.Label(main_frame, text="Choose how you want to run the file indexer:", font=("Arial", 10))
        desc_label.pack(pady=(0, 20))
        
        # Mode selection frame
        mode_frame = ttk.LabelFrame(main_frame, text="Launch Mode", padding="15")
        mode_frame.pack(fill=tk.X, pady=(0, 20))
        
        # GUI Mode
        gui_frame = ttk.Frame(mode_frame)
        gui_frame.pack(fill=tk.X, pady=(0, 10))
        
        gui_label = ttk.Label(gui_frame, text="GUI Mode", font=("Arial", 12, "bold"))
        gui_label.pack(anchor=tk.W)
        
        gui_desc = ttk.Label(gui_frame, text="Full interface with real-time file monitoring and suggestions", 
                           font=("Arial", 9), wraplength=300)
        gui_desc.pack(anchor=tk.W, pady=(5, 0))
        
        gui_button = ttk.Button(gui_frame, text="Launch GUI", command=self.launch_gui)
        gui_button.pack(anchor=tk.W, pady=(10, 0))
        
        # Separator
        separator = ttk.Separator(mode_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=10)
        
        # System Tray Mode
        tray_frame = ttk.Frame(mode_frame)
        tray_frame.pack(fill=tk.X)
        
        tray_label = ttk.Label(tray_frame, text="System Tray Mode", font=("Arial", 12, "bold"))
        tray_label.pack(anchor=tk.W)
        
        tray_desc = ttk.Label(tray_frame, text="Runs in background with system tray icon and notifications", 
                            font=("Arial", 9), wraplength=300)
        tray_desc.pack(anchor=tk.W, pady=(5, 0))
        
        tray_button = ttk.Button(tray_frame, text="Launch System Tray", command=self.launch_tray)
        tray_button.pack(anchor=tk.W, pady=(10, 0))
        
        # Bottom frame
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Install dependencies button
        install_button = ttk.Button(bottom_frame, text="Install Dependencies", command=self.install_dependencies)
        install_button.pack(side=tk.LEFT)
        
        # Exit button
        exit_button = ttk.Button(bottom_frame, text="Exit", command=self.root.destroy)
        exit_button.pack(side=tk.RIGHT)
    
    def launch_gui(self):
        """Launch the GUI version"""
        try:
            # Check if file_indexer.py exists
            if not os.path.exists("file_indexer.py"):
                messagebox.showerror("Error", "file_indexer.py not found!")
                return
            
            # Launch the GUI version without console window
            # Use pythonw.exe if available, otherwise use python.exe
            python_executable = self.get_pythonw_executable()
            subprocess.Popen([python_executable, "file_indexer.py"], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self.root.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch GUI: {e}")
    
    def launch_tray(self):
        """Launch the system tray version"""
        try:
            # Check if tray_indexer.py exists
            if not os.path.exists("tray_indexer.py"):
                messagebox.showerror("Error", "tray_indexer.py not found!")
                return
            
            # Launch the system tray version without console window
            # Use pythonw.exe if available, otherwise use python.exe
            python_executable = self.get_pythonw_executable()
            subprocess.Popen([python_executable, "tray_indexer.py"], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self.root.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch system tray: {e}")
    
    def install_dependencies(self):
        """Install Python dependencies"""
        try:
            # Check if requirements.txt exists
            if not os.path.exists("requirements.txt"):
                messagebox.showerror("Error", "requirements.txt not found!")
                return
            
            # Show progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Installing Dependencies")
            progress_window.geometry("300x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Center the progress window
            progress_window.update_idletasks()
            x = (progress_window.winfo_screenwidth() // 2) - (150 // 2)
            y = (progress_window.winfo_screenheight() // 2) - (75 // 2)
            progress_window.geometry(f"300x150+{x}+{y}")
            
            # Progress content
            ttk.Label(progress_window, text="Installing dependencies...", font=("Arial", 10)).pack(pady=20)
            
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=tk.X)
            progress_bar.start()
            
            # Run installation in background
            def install_thread():
                try:
                    # Use pythonw if available for pip install
                    pip_executable = self.get_pythonw_executable()
                    result = subprocess.run([pip_executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                                          capture_output=True, text=True, timeout=300)
                    
                    progress_window.after(0, lambda: self.handle_install_result(result, progress_window))
                    
                except subprocess.TimeoutExpired:
                    progress_window.after(0, lambda: self.handle_install_timeout(progress_window))
                except Exception as e:
                    progress_window.after(0, lambda: self.handle_install_error(str(e), progress_window))
            
            import threading
            threading.Thread(target=install_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start installation: {e}")
    
    def handle_install_result(self, result, progress_window):
        """Handle installation result"""
        progress_window.destroy()
        
        if result.returncode == 0:
            messagebox.showinfo("Success", "Dependencies installed successfully!")
        else:
            error_msg = f"Installation failed:\n{result.stderr}"
            messagebox.showerror("Error", error_msg)
    
    def handle_install_timeout(self, progress_window):
        """Handle installation timeout"""
        progress_window.destroy()
        messagebox.showerror("Error", "Installation timed out. Please try again.")
    
    def handle_install_error(self, error, progress_window):
        """Handle installation error"""
        progress_window.destroy()
        messagebox.showerror("Error", f"Installation error: {error}")
    
    def get_pythonw_executable(self):
        """Get the appropriate Python executable for running without console window"""
        try:
            # First try to find pythonw.exe in the same directory as the current Python executable
            python_dir = os.path.dirname(sys.executable)
            pythonw_path = os.path.join(python_dir, "pythonw.exe")
            
            if os.path.exists(pythonw_path):
                return pythonw_path
            
            # If not found, try to find pythonw.exe in PATH
            import shutil
            pythonw_in_path = shutil.which("pythonw.exe")
            if pythonw_in_path:
                return pythonw_in_path
            
            # Fallback to current Python executable
            return sys.executable
            
        except Exception:
            # Fallback to current Python executable
            return sys.executable
    
    def run(self):
        """Start the launcher"""
        self.root.mainloop()

def main():
    """Main entry point for the application"""
    app = LauncherGUI()
    app.run()

if __name__ == "__main__":
    main() 