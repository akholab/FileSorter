"""
Smart File Indexer - Main Application
A Python-based file indexing and organization system for Windows.
"""

import os
import platform
import json
import time
import threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import configparser
import psutil
from file_monitor import FileMonitor
from categorizer import categorize_file, describe_top, suggest_organization
from safemove import UndoLog, safe_move, trash_file, undo_move
from filewatch import get_settle_seconds, is_partial_name, is_still_changing
from learning import KEEP, Learner, get_threshold
import rules
import win32api
import win32gui
import subprocess

class FileIndexer:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = "file_indexer_config.ini"
        self.load_config()
        
        self.index_data = {}
        self.index_file = "file_index.json"
        self.load_index()
        
        # Categories come from rules.toml; on a mistake, the built-in ones are used
        # and rules_error says why (the GUI shows it at startup).
        self.categories, self.rules_error = rules.load()
        if self.rules_error:
            print(f"Rules not loaded, using built-in categories: {self.rules_error}")
        
        self.suggestions_queue = []
        self.is_running = False
        self.file_monitor = FileMonitor(self)
        self.last_user_activity = time.time()
        self.user_activity_threshold = 30  # seconds of inactivity before showing popups
        self.undo_log = UndoLog("file_undo_log.json")  # Last 500 actions, kept on disk
        self.last_error = ""  # Why the last execute_suggestion call returned False
        # Where you usually put each kind of file (extension + watched folder)
        self.learner = Learner("file_learned_choices.json", get_threshold(self.config))
        
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.config['DEFAULT'] = {
                'watch_directories': '',
                'auto_sort': 'True',
                'notification_delay': '30',
                'min_file_size': '1024',
                'exclude_extensions': '.tmp,.temp,.log,.cache,.bak',
                'exclude_folders': '$RECYCLE.BIN,System Volume Information,.git,__pycache__,node_modules',
                'include_extensions': '',
                'include_folders': ''
            }
            self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def load_index(self):
        """Load existing file index"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading index file: {e}")
                self.index_data = {}
    
    def save_index(self):
        """Save file index to disk"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving index file: {e}")
    
    def categorize_file(self, file_path):
        """Categorize a file based on extension and filename keywords"""
        return categorize_file(file_path, self.categories)
    
    def suggest_organization(self, file_path):
        """Generate organization suggestions for a file, with the folder you
        usually pick for this kind of file first"""
        suggestions = suggest_organization(file_path, self.categories)
        return self.learner.apply(file_path, suggestions, self.file_monitor.get_monitored_directories())
    
    def learn_from_move(self, source, destination, seen=None):
        """Count a move (or, with destination=None, a Keep) as a vote.

        Returns the details to store with the undo entry so Undo can take the
        vote back. Pass a set as `seen` so a bulk move counts once per group.
        """
        try:
            if destination is not None and os.path.normcase(str(Path(destination).parent)) == os.path.normcase(str(Path(source).parent)):
                return {}  # the file did not go anywhere: nothing to learn
            roots = self.file_monitor.get_monitored_directories()
            key = Learner.key_for(source, roots)
            if seen is not None:
                if key in seen:
                    return {}
                seen.add(key)
            key, dest = self.learner.vote(source, KEEP if destination is None else Path(destination).parent, roots)
            return {"learn_key": key, "learn_dest": dest}
        except Exception as e:
            # Learning is best effort: it must never make a finished move look failed
            print(f"Could not learn from this action: {e}")
            return {}
    
    def add_to_suggestions_queue(self, file_path):
        """Add a file to the suggestions queue for user review"""
        # Check if file is already in queue
        if file_path not in [s["file_path"] for s in self.suggestions_queue]:
            try:
                suggestions = self.suggest_organization(file_path)
                self.suggestions_queue.append({
                    "file_path": file_path,
                    "suggestions": suggestions,
                    "timestamp": datetime.now().isoformat()
                })
            except (OSError, ValueError) as e:
                print(f"Error adding {file_path} to suggestions queue: {e}")
    
    def get_next_suggestion(self):
        """Get the next suggestion from the queue"""
        if self.suggestions_queue:
            return self.suggestions_queue.pop(0)
        return None
    
    def record_action(self, action_type, file_path, details=None):
        """Record an action for undo functionality (saved to disk)"""
        self.undo_log.record(action_type, file_path, details)
    
    def undo_last_action(self):
        """Undo the last action performed"""
        last_action = self.undo_log.peek_last()
        if last_action is None:
            return False, "No actions to undo"
        
        try:
            success, message = self._undo_entry(last_action)
        except Exception as e:
            # Keep the entry in the log so the user can try again
            return False, f"Error undoing action: {e}"
        
        self.undo_log.pop_last()
        return success, message
    
    def _take_back_vote(self, action):
        """Undoing a move or a keep also takes back what it taught"""
        details = action.get("details") or {}
        if "learn_key" in details and "learn_dest" in details:
            self.learner.retract(details["learn_key"], details["learn_dest"])
    
    def _undo_entry(self, last_action):
        """Undo one logged action and return (success, message)"""
        if last_action["type"] == "moved":
            # Undo move: put the file back without overwriting anything
            current_path = Path(last_action["file_path"])
            success, message, _ = undo_move(last_action)
            if success:
                self._take_back_vote(last_action)
                # Remove from index
                if str(current_path) in self.index_data:
                    del self.index_data[str(current_path)]
                    self.save_index()
            return success, message
        
        elif last_action["type"] == "deleted":
            # Deleted files go to the Recycle Bin; restoring is manual
            file_path = Path(last_action["file_path"])
            return False, f"Cannot undo delete here: {file_path.name} is in the Recycle Bin. Restore it from there."
        
        elif last_action["type"] == "kept":
            # Undo keep: just remove from index
            self._take_back_vote(last_action)
            file_path = Path(last_action["file_path"])
            if str(file_path) in self.index_data:
                del self.index_data[str(file_path)]
                self.save_index()
            return True, f"Undid keep action for: {file_path.name}"
        
        else:
            return False, f"Unknown action type: {last_action['type']}"
    
    def move_blocker(self, file_path):
        """Return a message if the file must not be moved yet, else None.

        A file that was modified in the last few seconds is probably still
        being downloaded or copied. (`settle_seconds` in the config, default 5.)
        """
        if is_still_changing(file_path, get_settle_seconds(self.config)):
            return f"{Path(file_path).name} is still being written. Try again in a few seconds."
        return None
    
    def execute_suggestion(self, suggestion, action):
        """Execute a user-approved suggestion"""
        self.last_error = ""
        try:
            if action == "move":
                source = Path(suggestion["source"])
                destination = Path(suggestion["destination"])
                
                blocker = self.move_blocker(source)
                if blocker:
                    self.last_error = blocker
                    return False
                
                # Move the file (never overwrites; renames on a name clash)
                destination = safe_move(source, destination)
                
                # Record action for undo (and count it as a vote)
                details = {"original_path": str(source)}
                details.update(self.learn_from_move(source, destination))
                self.record_action("moved", destination, details)
                
                # Update index
                self.index_data[str(destination)] = {
                    "original_path": str(source),
                    "category": self.categorize_file(str(destination)),
                    "moved_at": datetime.now().isoformat(),
                    "action": "moved"
                }
                
            elif action == "keep":
                # Just update the index
                self.index_data[suggestion["source"]] = {
                    "category": self.categorize_file(suggestion["source"]),
                    "action": "kept",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Record action for undo (and count it as a vote)
                self.record_action("kept", Path(suggestion["source"]),
                                   self.learn_from_move(suggestion["source"], None))
            
            self.save_index()
            return True
            
        except Exception as e:
            print(f"Error executing suggestion: {e}")
            self.last_error = str(e)
            return False
    
    def should_process_file(self, file_path):
        """Check if file should be processed based on exclude/include rules"""
        try:
            path = Path(file_path)
            
            # Get exclude/include settings
            exclude_extensions = set(self.config.get('DEFAULT', 'exclude_extensions', fallback='').split(','))
            exclude_folders = set(self.config.get('DEFAULT', 'exclude_folders', fallback='').split(','))
            include_extensions = set(self.config.get('DEFAULT', 'include_extensions', fallback='').split(','))
            include_folders = set(self.config.get('DEFAULT', 'include_folders', fallback='').split(','))
            
            # Clean up empty strings
            exclude_extensions = {ext.strip() for ext in exclude_extensions if ext.strip()}
            exclude_folders = {folder.strip() for folder in exclude_folders if folder.strip()}
            include_extensions = {ext.strip() for ext in include_extensions if ext.strip()}
            include_folders = {folder.strip() for folder in include_folders if folder.strip()}
            
            # Skip unfinished downloads (.crdownload, .part, ...)
            if is_partial_name(path):
                return False
            
            # Check exclude extensions
            if path.suffix.lower() in exclude_extensions:
                return False
            
            # Check exclude folders
            for folder in exclude_folders:
                if folder in path.parts:
                    return False
            
            # Check include extensions (if specified, only process these)
            if include_extensions and path.suffix.lower() not in include_extensions:
                return False
            
            # Check include folders (if specified, only process files in these folders)
            if include_folders:
                found_included_folder = False
                for folder in include_folders:
                    if folder in path.parts:
                        found_included_folder = True
                        break
                if not found_included_folder:
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error checking file processing rules for {file_path}: {e}")
            return True  # Default to processing if there's an error
    
    def candidate_files(self, directory):
        """Yield the files under `directory` that the app would make suggestions
        for: processable by the include/exclude rules and not indexed yet."""
        for root, dirs, files in os.walk(directory):
            # Skip problematic directories
            dirs[:] = [d for d in dirs if d not in {'$RECYCLE.BIN', 'System Volume Information', '.git', '__pycache__'}]
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path) and self.should_process_file(file_path) \
                            and file_path not in self.index_data:
                        yield file_path
                except (OSError, PermissionError) as e:
                    print(f"Error processing file {file}: {e}")

    def preview_folder(self, directory):
        """List what sorting would do in `directory` without moving anything:
        one (file, destination folder or None, reason) per candidate file."""
        rows = []
        for file_path in self.candidate_files(directory):
            folder, reason = describe_top(self.suggest_organization(file_path), self.categorize_file(file_path))
            rows.append((file_path, folder, reason))
        return rows

    def scan_directory(self, directory):
        """Scan a directory for files and add them to the suggestions queue"""
        try:
            # Check if directory exists and is accessible
            if not os.path.exists(directory):
                print(f"Directory does not exist: {directory}")
                return
            
            if not os.path.isdir(directory):
                print(f"Path is not a directory: {directory}")
                return
            
            # Check permissions
            if not os.access(directory, os.R_OK):
                print(f"No read permission for directory: {directory}")
                return
            
            for file_path in self.candidate_files(directory):
                self.add_to_suggestions_queue(file_path)
                        
        except PermissionError as e:
            print(f"Permission denied scanning directory {directory}: {e}")
        except OSError as e:
            print(f"OS error scanning directory {directory}: {e}")
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
    
    def start_monitoring(self):
        """Start monitoring directories for changes"""
        self.is_running = True
        # Load monitored directories from config
        watch_dirs = self.config.get('DEFAULT', 'watch_directories', fallback='')
        if watch_dirs:
            for directory in watch_dirs.split(';'):
                if directory.strip():
                    self.file_monitor.add_directory(directory.strip())
        
        self.file_monitor.start()
        print("File monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring directories"""
        self.is_running = False
        self.file_monitor.stop()
        print("File monitoring stopped")
    
    def add_monitored_directory(self, directory):
        """Add a directory to monitoring"""
        if self.file_monitor.add_directory(directory):
            # Save to config
            current_dirs = self.config.get('DEFAULT', 'watch_directories', fallback='')
            if current_dirs:
                current_dirs += ';' + directory
            else:
                current_dirs = directory
            self.config['DEFAULT']['watch_directories'] = current_dirs
            self.save_config()
            return True
        return False
    
    def remove_monitored_directory(self, directory):
        """Remove a directory from monitoring"""
        if self.file_monitor.remove_directory(directory):
            # Remove from config
            current_dirs = self.config.get('DEFAULT', 'watch_directories', fallback='')
            if current_dirs:
                dir_list = current_dirs.split(';')
                if directory in dir_list:
                    dir_list.remove(directory)
                    self.config['DEFAULT']['watch_directories'] = ';'.join(dir_list)
                    self.save_config()
            return True
        return False

class FileIndexerGUI:
    def __init__(self):
        self.indexer = FileIndexer()
        self.root = tk.Tk()
        self.root.title("Smart File Indexer")
        self.root.geometry("800x600")
        
        self.setup_ui()
        if self.indexer.rules_error:
            messagebox.showwarning("Rules not loaded",
                                   f"Using the built-in categories because of a problem in "
                                   f"{self.indexer.rules_error}")
        self.check_suggestions()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Smart File Indexer", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        ttk.Button(button_frame, text="Scan Directory", command=self.scan_directory).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Add Monitor", command=self.add_monitor).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(button_frame, text="Get Suggestions", command=self.get_suggestions).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(button_frame, text="Preview Sorting", command=self.preview_sorting).grid(row=0, column=3, padx=(0, 10))
        ttk.Button(button_frame, text="Settings", command=self.show_settings).grid(row=0, column=4)
        
        # Suggestions frame
        suggestions_frame = ttk.LabelFrame(main_frame, text="File Suggestions", padding="10")
        suggestions_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Suggestions list - Tree view for hierarchical display
        self.suggestions_tree = ttk.Treeview(suggestions_frame, columns=("Path", "Category", "Action"), show="tree headings")
        self.suggestions_tree.heading("#0", text="Files & Folders")  # Tree column
        self.suggestions_tree.heading("Path", text="Path")
        self.suggestions_tree.heading("Category", text="Category")
        self.suggestions_tree.heading("Action", text="Action")
        
        # Set column widths
        self.suggestions_tree.column("#0", width=250)  # Tree column
        self.suggestions_tree.column("Path", width=200)
        self.suggestions_tree.column("Category", width=100)
        self.suggestions_tree.column("Action", width=100)
        
        self.suggestions_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar for suggestions
        suggestions_scrollbar = ttk.Scrollbar(suggestions_frame, orient=tk.VERTICAL, command=self.suggestions_tree.yview)
        suggestions_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.suggestions_tree.configure(yscrollcommand=suggestions_scrollbar.set)
        
        # Action buttons for suggestions
        action_frame = ttk.Frame(suggestions_frame)
        action_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        
        # File actions
        file_actions_frame = ttk.LabelFrame(action_frame, text="File Actions", padding="5")
        file_actions_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Button(file_actions_frame, text="Preview", command=self.preview_file).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(file_actions_frame, text="Move", command=self.move_file).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(file_actions_frame, text="Keep", command=self.keep_file).grid(row=0, column=2, padx=(0, 5))
        ttk.Button(file_actions_frame, text="Delete", command=self.delete_file).grid(row=0, column=3, padx=(0, 5))
        ttk.Button(file_actions_frame, text="Skip", command=self.skip_file).grid(row=0, column=4, padx=(0, 5))
        
        # Directory actions
        dir_actions_frame = ttk.LabelFrame(action_frame, text="Directory Actions", padding="5")
        dir_actions_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Button(dir_actions_frame, text="Move All Files", command=self.move_directory_files).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(dir_actions_frame, text="Keep All Files", command=self.keep_directory_files).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(dir_actions_frame, text="Skip All Files", command=self.skip_directory_files).grid(row=0, column=2, padx=(0, 5))
        
        # Undo button
        ttk.Button(action_frame, text="Undo Last Action", command=self.undo_last_action).grid(row=2, column=0, columnspan=2, pady=(5, 0))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        suggestions_frame.columnconfigure(0, weight=1)
        suggestions_frame.rowconfigure(0, weight=1)
        
        # Start monitoring on startup
        self.indexer.start_monitoring()
        
        # Bind double-click event
        self.suggestions_tree.bind("<Double-1>", self.on_suggestion_double_click)
        
        # Bind user activity events
        self.root.bind("<Key>", self.on_user_activity)
        self.root.bind("<Button-1>", self.on_user_activity)
        self.root.bind("<Motion>", self.on_user_activity)
        self.suggestions_tree.bind("<Key>", self.on_user_activity)
        self.suggestions_tree.bind("<Button-1>", self.on_user_activity)
    
    def scan_directory(self):
        """Scan a directory for files"""
        directory = filedialog.askdirectory(title="Select directory to scan")
        if directory:
            self.status_label.config(text=f"Scanning {directory}...")
            self.root.update()
            
            # Run scanning in a separate thread
            def scan_thread():
                self.indexer.scan_directory(directory)
                self.root.after(0, lambda: self.status_label.config(text="Scan complete"))
                self.root.after(0, self.update_suggestions_list)
            
            threading.Thread(target=scan_thread, daemon=True).start()
    
    def preview_sorting(self):
        """Show where each file in a folder would go and why. Moves nothing."""
        watched = self.indexer.file_monitor.get_monitored_directories()
        directory = filedialog.askdirectory(title="Select folder to preview",
                                            initialdir=watched[0] if watched else None)
        if not directory:
            return
        rows = self.indexer.preview_folder(directory)

        window = tk.Toplevel(self.root)
        window.title(f"Preview: {directory}")
        window.geometry("800x400")
        ttk.Label(window, text="Nothing is moved here. This shows what sorting would suggest first.").pack(pady=5)
        frame = ttk.Frame(window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tree = ttk.Treeview(frame, columns=("File", "Destination", "Why"), show="headings")
        for column, width in (("File", 300), ("Destination", 300), ("Why", 150)):
            tree.heading(column, text=column)
            tree.column(column, width=width)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for file_path, folder, reason in rows:
            tree.insert("", tk.END, values=(os.path.relpath(file_path, directory), folder or "(stays here)", reason))
        if not rows:
            tree.insert("", tk.END, values=("No files to sort here", "", ""))
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=5)

    def add_monitor(self):
        """Add a directory to monitoring"""
        directory = filedialog.askdirectory(title="Select directory to monitor")
        if directory:
            if self.indexer.add_monitored_directory(directory):
                messagebox.showinfo("Success", f"Added {directory} to monitoring")
                self.update_status()
            else:
                messagebox.showerror("Error", f"Failed to add {directory} to monitoring")
    
    def get_suggestions(self):
        """Get suggestions for files"""
        self.update_suggestions_list()
        if self.indexer.suggestions_queue:
            self.show_suggestion_popup()
    
    def get_file_icon(self, file_path):
        """Get appropriate icon for file type"""
        extension = file_path.suffix.lower()
        
        # Document icons
        if extension in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
            return "📄"
        elif extension in ['.xls', '.xlsx', '.csv']:
            return "📊"
        elif extension in ['.ppt', '.pptx']:
            return "📈"
        
        # Media icons
        elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return "🖼️"
        elif extension in ['.mp4', '.avi', '.mov', '.wmv']:
            return "🎥"
        elif extension in ['.mp3', '.wav', '.flac']:
            return "🎵"
        
        # Archive icons
        elif extension in ['.zip', '.rar', '.7z', '.tar']:
            return "📦"
        
        # Code icons
        elif extension in ['.py', '.js', '.html', '.css', '.java']:
            return "💻"
        
        # Default file icon
        else:
            return "📄"
    
    def update_suggestions_list(self):
        """Update the suggestions list display with hierarchical structure"""
        # Clear existing items
        for item in self.suggestions_tree.get_children():
            self.suggestions_tree.delete(item)
        
        # Group files by directory hierarchy
        directory_hierarchy = {}
        
        # First pass: collect all files and their directories
        for i, suggestion in enumerate(self.indexer.suggestions_queue):
            file_path = Path(suggestion["file_path"])
            parent_dir = str(file_path.parent)
            
            # Initialize parent directory if not exists
            if parent_dir not in directory_hierarchy:
                directory_hierarchy[parent_dir] = {"files": [], "subdirs": {}}
            
            # Add file to its parent directory
            directory_hierarchy[parent_dir]["files"].append((i, suggestion, file_path))
        
        # Second pass: build the complete hierarchy by finding common ancestors
        complete_hierarchy = {}
        
        for dir_path in directory_hierarchy.keys():
            path_obj = Path(dir_path)
            path_parts = list(path_obj.parts)
            
            # Build hierarchy from root to this directory
            current_dict = complete_hierarchy
            for i, part in enumerate(path_parts):
                current_path = str(Path(*path_parts[:i+1]))
                
                if current_path not in current_dict:
                    current_dict[current_path] = {"files": [], "subdirs": {}}
                
                # If this is the directory that contains files, add them
                if current_path == dir_path:
                    current_dict[current_path]["files"] = directory_hierarchy[dir_path]["files"]
                
                current_dict = current_dict[current_path]["subdirs"]
        
        # Recursively build tree, but only show directories that have files or subdirectories with files
        self._build_tree_recursive("", complete_hierarchy)
    
    def _build_tree_recursive(self, parent_item, hierarchy):
        """Recursively build the tree structure"""
        for directory, content in hierarchy.items():
            dir_path = Path(directory)
            dir_name = dir_path.name if dir_path.name else str(dir_path)
            
            # Count files by category in this directory
            category_counts = {}
            total_files = len(content["files"])
            
            # Count files in this directory
            for _, suggestion, file_path in content["files"]:
                category = self.indexer.categorize_file(suggestion["file_path"])
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Check if this directory has files or non-empty subdirectories
            has_files = total_files > 0
            has_subdirs_with_files = False
            
            # Check subdirectories recursively
            non_empty_subdirs = {}
            for subdir_name, subdir_content in content["subdirs"].items():
                # Recursively check if this subdirectory has files
                subdir_has_content = self._has_files_recursive(subdir_content)
                if subdir_has_content:
                    has_subdirs_with_files = True
                    non_empty_subdirs[subdir_name] = subdir_content
            
            # Only show directories that have files or non-empty subdirectories
            if has_files or has_subdirs_with_files:
                # Create directory display text
                dir_display = f"📁 {dir_name} ({total_files} files)"
                if category_counts:
                    categories_text = ", ".join([f"{cat}: {count}" for cat, count in category_counts.items()])
                    dir_display += f" - {categories_text}"
                
                # Insert directory node
                dir_item = self.suggestions_tree.insert(parent_item, "end", 
                    text=dir_display,
                    values=(directory, "Directory", "Review needed"),
                    tags=("directory", directory),
                    open=True  # Start expanded
                )
                
                # Add files under this directory
                for i, suggestion, file_path in content["files"]:
                    category = self.indexer.categorize_file(suggestion["file_path"])
                    icon = self.get_file_icon(file_path)
                    
                    self.suggestions_tree.insert(dir_item, "end",
                        text=f"{icon} {file_path.name}",
                        values=(str(file_path), category, "Review needed"),
                        tags=(str(i), "file")
                    )
                
                # Recursively add non-empty subdirectories
                if non_empty_subdirs:
                    self._build_tree_recursive(dir_item, non_empty_subdirs)
    
    def _has_files_recursive(self, content):
        """Recursively check if a directory content has any files"""
        if len(content["files"]) > 0:
            return True
        
        for subdir_content in content["subdirs"].values():
            if self._has_files_recursive(subdir_content):
                return True
        
        return False
    
    def show_suggestion_popup(self):
        """Show a popup for the next suggestion"""
        if not self.indexer.suggestions_queue:
            return
        
        suggestion = self.indexer.suggestions_queue[0]
        file_path = Path(suggestion["file_path"])
        
        popup = tk.Toplevel(self.root)
        popup.title("File Organization Suggestion")
        popup.geometry("500x400")
        popup.transient(self.root)
        popup.grab_set()
        
        # Center the popup
        popup.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # Popup content
        ttk.Label(popup, text=f"File: {file_path.name}", font=("Arial", 12, "bold")).pack(pady=10)
        ttk.Label(popup, text=f"Location: {file_path.parent}", font=("Arial", 10)).pack(pady=5)
        
        # Suggestions list
        suggestions_frame = ttk.LabelFrame(popup, text="Suggested Actions", padding="10")
        suggestions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        suggestions_listbox = tk.Listbox(suggestions_frame)
        suggestions_listbox.pack(fill=tk.BOTH, expand=True)
        
        for suggestion_option in suggestion["suggestions"]:
            if suggestion_option["action"] == "move":
                display_text = f"Move to: {Path(suggestion_option['destination']).parent}"
            else:
                display_text = "Keep in current location"
            if suggestion_option.get("learned_count"):
                display_text += f"  (your usual, {suggestion_option['learned_count']} times)"
            suggestions_listbox.insert(tk.END, display_text)
        
        # Action buttons
        button_frame = ttk.Frame(popup)
        button_frame.pack(pady=10)
        
        def execute_action():
            selection = suggestions_listbox.curselection()
            if selection:
                selected_suggestion = suggestion["suggestions"][selection[0]]
                if selected_suggestion["action"] == "move":
                    done = self.indexer.execute_suggestion(selected_suggestion, "move")
                else:
                    done = self.indexer.execute_suggestion(selected_suggestion, "keep")
                if not done:
                    # Keep the file in the queue and the popup open
                    messagebox.showwarning("Could not complete", self.indexer.last_error or "Failed to organize file")
                    return
                
                # Remove from queue
                self.indexer.suggestions_queue.pop(0)
                popup.destroy()
                self.update_suggestions_list()
        
        ttk.Button(button_frame, text="Execute", command=execute_action).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Skip", command=lambda: [self.indexer.suggestions_queue.pop(0), popup.destroy(), self.update_suggestions_list()]).pack(side=tk.LEFT)
    
    def move_file(self):
        """Move the selected file"""
        item_type, index, item = self.get_selected_items()
        
        if item_type != "file":
            messagebox.showwarning("Selection", "Please select a file to move")
            return
        
        suggestion = self.indexer.suggestions_queue[index]
        
        # Let user choose destination
        destination = filedialog.askdirectory(
            title=f"Choose destination for {Path(suggestion['file_path']).name}",
            initialdir=Path(suggestion['file_path']).parent
        )
        
        if destination:
            try:
                source_path = Path(suggestion["file_path"])
                dest_path = Path(destination) / source_path.name
                
                blocker = self.indexer.move_blocker(source_path)
                if blocker:
                    messagebox.showwarning("Not moved", blocker)
                    return
                
                # Move the file (never overwrites; renames on a name clash)
                dest_path = safe_move(source_path, dest_path)
                
                # Record action for undo (and count it as a vote)
                details = {"original_path": str(source_path)}
                details.update(self.indexer.learn_from_move(source_path, dest_path))
                self.indexer.record_action("moved", dest_path, details)
                
                # Update index
                self.indexer.index_data[str(dest_path)] = {
                    "original_path": str(source_path),
                    "category": self.indexer.categorize_file(str(dest_path)),
                    "moved_at": datetime.now().isoformat(),
                    "action": "moved"
                }
                self.indexer.save_index()
                
                # Remove from queue
                self.indexer.suggestions_queue.pop(index)
                self.update_suggestions_list()
                messagebox.showinfo("Success", f"File moved to {dest_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to move file: {e}")
    
    def keep_file(self):
        """Keep the selected file in current location"""
        item_type, index, item = self.get_selected_items()
        
        if item_type != "file":
            messagebox.showwarning("Selection", "Please select a file to keep")
            return
        
        suggestion = self.indexer.suggestions_queue[index]
        
        # Find keep suggestion
        for suggestion_option in suggestion["suggestions"]:
            if suggestion_option["action"] == "keep":
                if self.indexer.execute_suggestion(suggestion_option, "keep"):
                    self.indexer.suggestions_queue.pop(index)
                    self.update_suggestions_list()
                    messagebox.showinfo("Success", "File kept in current location!")
                else:
                    messagebox.showwarning("Could not complete", self.indexer.last_error or "Failed to keep file")
                break
    
    def preview_file(self):
        """Preview the selected file"""
        item_type, index, item = self.get_selected_items()
        
        if item_type != "file":
            messagebox.showwarning("Selection", "Please select a file to preview")
            return
        
        suggestion = self.indexer.suggestions_queue[index]
        file_path = Path(suggestion["file_path"])
        
        try:
            if platform.system() == "Windows":
                # Use Windows default application
                os.startfile(str(file_path))
            else:
                # Use xdg-open on Linux or open on macOS
                subprocess.run(["xdg-open" if platform.system() == "Linux" else "open", str(file_path)])
            
            messagebox.showinfo("Preview", f"Opening {file_path.name} with default application")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not preview file: {e}")
    
    def delete_file(self):
        """Delete the selected file"""
        item_type, index, item = self.get_selected_items()
        
        if item_type != "file":
            messagebox.showwarning("Selection", "Please select a file to delete")
            return
        
        suggestion = self.indexer.suggestions_queue[index]
        file_path = Path(suggestion["file_path"])
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Delete", 
            f"Move to the Recycle Bin:\n{file_path.name}\n\nYou can restore it from the Recycle Bin.",
            icon='warning'
        )
        
        if result:
            try:
                # Send the file to the Recycle Bin (never deletes it for good)
                trash_file(file_path)
                
                # Record the action in the undo log
                self.indexer.record_action("deleted", file_path)
                
                # Remove from queue
                self.indexer.suggestions_queue.pop(index)
                self.update_suggestions_list()
                
                messagebox.showinfo("Success", f"Moved to the Recycle Bin: {file_path.name}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {e}")
    
    def undo_last_action(self):
        """Undo the last action performed"""
        success, message = self.indexer.undo_last_action()
        
        if success:
            messagebox.showinfo("Undo Successful", message)
            # Refresh the suggestions list
            self.update_suggestions_list()
        else:
            messagebox.showwarning("Undo Failed", message)
    
    def get_selected_items(self):
        """Get selected items and determine if it's a directory or file"""
        selection = self.suggestions_tree.selection()
        if not selection:
            return None, None, None
        
        item = self.suggestions_tree.item(selection[0])
        tags = item["tags"]
        
        # Check if it's a directory
        if "directory" in tags:
            directory = tags[1]  # Directory path is stored in second tag
            return "directory", directory, item
        else:
            # It's a file
            index = int(tags[0])
            return "file", index, item
    
    def move_directory_files(self):
        """Move all files in the selected directory and subdirectories"""
        item_type, directory, item = self.get_selected_items()
        
        if item_type != "directory":
            messagebox.showwarning("Selection", "Please select a directory to move all files")
            return
        
        # Let user choose destination
        destination = filedialog.askdirectory(
            title=f"Choose destination for all files in {Path(directory).name}",
            initialdir=Path(directory).parent
        )
        
        if destination:
            try:
                moved_count = 0
                failed_count = 0
                learned_groups = set()
                
                # Find all files in this directory and subdirectories
                files_to_move = []
                for i, suggestion in enumerate(self.indexer.suggestions_queue):
                    file_path = Path(suggestion["file_path"])
                    # Check if file is in this directory or any subdirectory
                    if str(file_path.parent) == directory or str(file_path.parent).startswith(directory + os.sep):
                        files_to_move.append((i, suggestion, file_path))
                
                # Move files in reverse order to maintain indices
                for i, suggestion, file_path in reversed(files_to_move):
                    try:
                        dest_path = Path(destination) / file_path.name
                        
                        # Skip files that are still being written; they stay in the queue
                        blocker = self.indexer.move_blocker(file_path)
                        if blocker:
                            print(blocker)
                            failed_count += 1
                            continue
                        
                        # Move the file (never overwrites; renames on a name clash)
                        dest_path = safe_move(file_path, dest_path)
                        
                        # Record action for undo (a bulk move is one vote per kind of file)
                        details = {"original_path": str(file_path)}
                        details.update(self.indexer.learn_from_move(file_path, dest_path, learned_groups))
                        self.indexer.record_action("moved", dest_path, details)
                        
                        # Update index
                        self.indexer.index_data[str(dest_path)] = {
                            "original_path": str(file_path),
                            "category": self.indexer.categorize_file(str(dest_path)),
                            "moved_at": datetime.now().isoformat(),
                            "action": "moved"
                        }
                        
                        # Remove from queue
                        self.indexer.suggestions_queue.pop(i)
                        moved_count += 1
                        
                    except Exception as e:
                        print(f"Failed to move {file_path.name}: {e}")
                        failed_count += 1
                
                self.indexer.save_index()
                self.update_suggestions_list()
                
                message = f"Moved {moved_count} files to {destination}"
                if failed_count > 0:
                    message += f"\nFailed to move {failed_count} files"
                
                messagebox.showinfo("Move Complete", message)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to move directory files: {e}")
    
    def keep_directory_files(self):
        """Keep all files in the selected directory and subdirectories"""
        item_type, directory, item = self.get_selected_items()
        
        if item_type != "directory":
            messagebox.showwarning("Selection", "Please select a directory to keep all files")
            return
        
        try:
            kept_count = 0
            learned_groups = set()
            
            # Find all files in this directory and subdirectories
            files_to_keep = []
            for i, suggestion in enumerate(self.indexer.suggestions_queue):
                file_path = Path(suggestion["file_path"])
                # Check if file is in this directory or any subdirectory
                if str(file_path.parent) == directory or str(file_path.parent).startswith(directory + os.sep):
                    files_to_keep.append((i, suggestion, file_path))
            
            # Keep files in reverse order to maintain indices
            for i, suggestion, file_path in reversed(files_to_keep):
                try:
                    # Update index
                    self.indexer.index_data[str(file_path)] = {
                        "category": self.indexer.categorize_file(str(file_path)),
                        "action": "kept",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Record action for undo (a bulk keep is one vote per kind of file)
                    self.indexer.record_action("kept", file_path,
                                               self.indexer.learn_from_move(file_path, None, learned_groups))
                    
                    # Remove from queue
                    self.indexer.suggestions_queue.pop(i)
                    kept_count += 1
                    
                except Exception as e:
                    print(f"Failed to keep {file_path.name}: {e}")
            
            self.indexer.save_index()
            self.update_suggestions_list()
            
            messagebox.showinfo("Keep Complete", f"Kept {kept_count} files in their current locations")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to keep directory files: {e}")
    
    def skip_directory_files(self):
        """Skip all files in the selected directory and subdirectories"""
        item_type, directory, item = self.get_selected_items()
        
        if item_type != "directory":
            messagebox.showwarning("Selection", "Please select a directory to skip all files")
            return
        
        try:
            skipped_count = 0
            
            # Find all files in this directory and subdirectories
            files_to_skip = []
            for i, suggestion in enumerate(self.indexer.suggestions_queue):
                file_path = Path(suggestion["file_path"])
                # Check if file is in this directory or any subdirectory
                if str(file_path.parent) == directory or str(file_path.parent).startswith(directory + os.sep):
                    files_to_skip.append((i, suggestion, file_path))
            
            # Skip files in reverse order to maintain indices
            for i, suggestion, file_path in reversed(files_to_skip):
                try:
                    # Remove from queue
                    self.indexer.suggestions_queue.pop(i)
                    skipped_count += 1
                    
                except Exception as e:
                    print(f"Failed to skip {file_path.name}: {e}")
            
            self.update_suggestions_list()
            
            messagebox.showinfo("Skip Complete", f"Skipped {skipped_count} files")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to skip directory files: {e}")
    
    def skip_file(self):
        """Skip the selected file"""
        item_type, index, item = self.get_selected_items()
        
        if item_type != "file":
            messagebox.showwarning("Selection", "Please select a file to skip")
            return
        
        self.indexer.suggestions_queue.pop(index)
        self.update_suggestions_list()
    
    def on_user_activity(self, event):
        """Track user activity with improved detection"""
        # Update activity timestamp
        self.indexer.last_user_activity = time.time()
        
        # Check if user is actively typing or clicking
        if hasattr(event, 'keysym') or hasattr(event, 'char'):
            # Keyboard activity - extend the activity window
            self.indexer.last_user_activity = time.time() + 5  # Add 5 seconds buffer
        elif hasattr(event, 'num'):
            # Mouse activity
            self.indexer.last_user_activity = time.time() + 2  # Add 2 seconds buffer
    
    def on_suggestion_double_click(self, event):
        """Handle double-click on suggestion"""
        self.on_user_activity(event)  # Track activity
        self.show_suggestion_popup()
    
    def show_settings(self):
        """Show settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x400")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Settings content
        ttk.Label(settings_window, text="File Indexer Settings", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Auto-sort setting
        auto_sort_var = tk.BooleanVar(value=self.indexer.config.getboolean('DEFAULT', 'auto_sort', fallback=True))
        ttk.Checkbutton(settings_window, text="Auto-sort files", variable=auto_sort_var).pack(pady=5)
        
        # Notification delay
        ttk.Label(settings_window, text="Notification delay (seconds):").pack(pady=5)
        delay_var = tk.StringVar(value=self.indexer.config.get('DEFAULT', 'notification_delay', fallback='30'))
        ttk.Entry(settings_window, textvariable=delay_var).pack(pady=5)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # General settings tab
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        
        # Monitored directories
        ttk.Label(general_frame, text="Monitored Directories:", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        
        monitored_frame = ttk.Frame(general_frame)
        monitored_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # List of monitored directories
        monitored_listbox = tk.Listbox(monitored_frame, height=6)
        monitored_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        monitored_scrollbar = ttk.Scrollbar(monitored_frame, orient=tk.VERTICAL, command=monitored_listbox.yview)
        monitored_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        monitored_listbox.configure(yscrollcommand=monitored_scrollbar.set)
        
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
        
        ttk.Button(general_frame, text="Remove Selected Directory", command=remove_directory).pack(pady=5)
        
        # File filtering tab
        filter_frame = ttk.Frame(notebook)
        notebook.add(filter_frame, text="File Filtering")
        
        # Exclude extensions
        ttk.Label(filter_frame, text="Exclude Extensions (comma-separated):", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        exclude_ext_var = tk.StringVar(value=self.indexer.config.get('DEFAULT', 'exclude_extensions', fallback='.tmp,.temp,.log,.cache,.bak'))
        exclude_ext_entry = ttk.Entry(filter_frame, textvariable=exclude_ext_var, width=50)
        exclude_ext_entry.pack(pady=(0, 10))
        
        # Exclude folders
        ttk.Label(filter_frame, text="Exclude Folders (comma-separated):", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        exclude_folder_var = tk.StringVar(value=self.indexer.config.get('DEFAULT', 'exclude_folders', fallback='$RECYCLE.BIN,System Volume Information,.git,__pycache__,node_modules'))
        exclude_folder_entry = ttk.Entry(filter_frame, textvariable=exclude_folder_var, width=50)
        exclude_folder_entry.pack(pady=(0, 10))
        
        # Include extensions
        ttk.Label(filter_frame, text="Include Only Extensions (leave empty for all):", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        include_ext_var = tk.StringVar(value=self.indexer.config.get('DEFAULT', 'include_extensions', fallback=''))
        include_ext_entry = ttk.Entry(filter_frame, textvariable=include_ext_var, width=50)
        include_ext_entry.pack(pady=(0, 10))
        
        # Include folders
        ttk.Label(filter_frame, text="Include Only Folders (leave empty for all):", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        include_folder_var = tk.StringVar(value=self.indexer.config.get('DEFAULT', 'include_folders', fallback=''))
        include_folder_entry = ttk.Entry(filter_frame, textvariable=include_folder_var, width=50)
        include_folder_entry.pack(pady=(0, 10))
        
        # Save button
        def save_settings():
            self.indexer.config['DEFAULT']['auto_sort'] = str(auto_sort_var.get())
            self.indexer.config['DEFAULT']['notification_delay'] = delay_var.get()
            self.indexer.config['DEFAULT']['exclude_extensions'] = exclude_ext_var.get()
            self.indexer.config['DEFAULT']['exclude_folders'] = exclude_folder_var.get()
            self.indexer.config['DEFAULT']['include_extensions'] = include_ext_var.get()
            self.indexer.config['DEFAULT']['include_folders'] = include_folder_var.get()
            self.indexer.save_config()
            settings_window.destroy()
            messagebox.showinfo("Settings", "Settings saved successfully!")
        
        ttk.Button(settings_window, text="Save", command=save_settings).pack(pady=20)
    
    def update_status(self):
        """Update the status display"""
        monitored_count = len(self.indexer.file_monitor.get_monitored_directories())
        suggestions_count = len(self.indexer.suggestions_queue)
        
        status_text = f"Monitoring {monitored_count} directories | {suggestions_count} pending suggestions"
        self.status_label.config(text=status_text)
    
    def check_user_activity(self):
        """Check if user is actively using the computer"""
        try:
            # Get cursor position
            cursor_pos = win32api.GetCursorPos()
            
            # Get foreground window
            foreground_window = win32gui.GetForegroundWindow()
            
            # Check if our application is the foreground window
            if foreground_window == self.root.winfo_id():
                self.last_user_activity = time.time()
                return True
            
            # Check if cursor has moved significantly (indicating activity)
            # This is a simple heuristic - you could make it more sophisticated
            return True  # For now, assume user is active if our app is focused
            
        except Exception as e:
            print(f"Error checking user activity: {e}")
            return True  # Default to assuming user is active
    
    def check_suggestions(self):
        """Periodically check for new suggestions"""
        self.update_status()
        
        # Check if user has been inactive for the threshold period
        time_since_activity = time.time() - self.indexer.last_user_activity
        
        # Only show notifications if:
        # 1. There are suggestions
        # 2. User has been inactive for threshold period
        # 3. Application is not focused
        # 4. User is not actively typing (extended buffer)
        if (self.indexer.suggestions_queue and 
            time_since_activity > self.indexer.user_activity_threshold and 
            not self.root.focus_get() and
            time_since_activity > 10):  # Additional 10-second buffer for typing
            # Show notification if there are pending suggestions and user is inactive
            self.show_notification()
        
        # Schedule next check
        self.root.after(30000, self.check_suggestions)  # Check every 30 seconds
    
    def show_notification(self):
        """Show a non-intrusive notification"""
        notification = tk.Toplevel(self.root)
        notification.title("File Suggestions Available")
        notification.geometry("350x120")
        notification.attributes('-topmost', True)
        notification.configure(bg='#f0f0f0')
        
        # Position in bottom-right corner
        x = self.root.winfo_screenwidth() - 370
        y = self.root.winfo_screenheight() - 140
        notification.geometry(f"+{x}+{y}")
        
        # Make it look more like a system notification
        notification.overrideredirect(True)  # Remove window decorations
        
        # Create a frame with border
        frame = tk.Frame(notification, bg='#2c3e50', relief='raised', bd=2)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Content frame
        content_frame = tk.Frame(frame, bg='white')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Title
        title_label = tk.Label(content_frame, text="📁 File Organization", 
                              font=("Arial", 11, "bold"), bg='white', fg='#2c3e50')
        title_label.pack(pady=(5, 2))
        
        # Message
        msg_label = tk.Label(content_frame, text=f"You have {len(self.indexer.suggestions_queue)} file(s) to organize", 
                            font=("Arial", 9), bg='white', fg='#34495e')
        msg_label.pack(pady=(0, 5))
        
        # Button frame
        button_frame = tk.Frame(content_frame, bg='white')
        button_frame.pack(pady=(0, 5))
        
        # Buttons
        review_btn = tk.Button(button_frame, text="Review Now", 
                              command=lambda: [notification.destroy(), self.get_suggestions()],
                              bg='#3498db', fg='white', relief='flat', padx=10)
        review_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        dismiss_btn = tk.Button(button_frame, text="Later", 
                               command=notification.destroy,
                               bg='#95a5a6', fg='white', relief='flat', padx=10)
        dismiss_btn.pack(side=tk.LEFT)
        
        # Auto-dismiss after 15 seconds
        notification.after(15000, notification.destroy)
        
        # Fade in effect
        notification.attributes('-alpha', 0.0)
        for i in range(10):
            notification.after(i * 50, lambda alpha=i/10: notification.attributes('-alpha', alpha))
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = FileIndexerGUI()
    app.run() 