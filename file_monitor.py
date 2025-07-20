"""
File monitoring module for the Smart File Indexer.
Handles real-time file system monitoring and event processing.
"""

import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, indexer):
        self.indexer = indexer
        self.ignored_extensions = {'.tmp', '.temp', '.log', '.cache'}
        self.ignored_folders = {'$RECYCLE.BIN', 'System Volume Information', '.git', '__pycache__'}
    
    def on_created(self, event):
        if not event.is_directory:
            try:
                # Handle different watchdog versions
                if hasattr(event, 'src_path'):
                    file_path = event.src_path
                elif hasattr(event, 'source_path'):
                    file_path = event.source_path
                else:
                    file_path = str(event)
                
                if self._should_process_file(file_path):
                    print(f"New file detected: {file_path}")
                    # Add to suggestions queue
                    self.indexer.add_to_suggestions_queue(file_path)
            except Exception as e:
                print(f"Error processing created event: {e}")
    
    def on_moved(self, event):
        if not event.is_directory:
            try:
                # Handle different watchdog versions
                if hasattr(event, 'dest_path'):
                    file_path = event.dest_path
                elif hasattr(event, 'destination_path'):
                    file_path = event.destination_path
                else:
                    file_path = str(event)
                
                if self._should_process_file(file_path):
                    print(f"File moved: {file_path}")
                    # Add to suggestions queue
                    self.indexer.add_to_suggestions_queue(file_path)
            except Exception as e:
                print(f"Error processing moved event: {e}")
    
    def _should_process_file(self, file_path):
        """Check if file should be processed"""
        path = Path(file_path)
        
        # Check ignored extensions
        if path.suffix.lower() in self.ignored_extensions:
            return False
        
        # Check ignored folders
        for folder in self.ignored_folders:
            if folder in path.parts:
                return False
        
        # Check if file exists and is not a directory
        if not path.is_file():
            return False
        
        # Check minimum file size (1KB)
        try:
            if path.stat().st_size < 1024:
                return False
        except OSError:
            return False
        
        return True

class FileMonitor:
    def __init__(self, indexer):
        self.indexer = indexer
        self.observer = Observer()
        self.monitored_paths = set()
        self.is_running = False
    
    def add_directory(self, directory):
        """Add a directory to monitor"""
        if directory not in self.monitored_paths:
            try:
                event_handler = FileChangeHandler(self.indexer)
                self.observer.schedule(event_handler, directory, recursive=True)
                self.monitored_paths.add(directory)
                print(f"Added directory to monitor: {directory}")
                return True
            except OSError as e:
                print(f"Error adding directory {directory}: {e}")
                return False
        return False
    
    def remove_directory(self, directory):
        """Remove a directory from monitoring"""
        if directory in self.monitored_paths:
            try:
                # Find and remove the schedule for this directory
                for schedule in self.observer.schedules():
                    if schedule.path == directory:
                        self.observer.unschedule(schedule)
                        break
                self.monitored_paths.remove(directory)
                print(f"Removed directory from monitor: {directory}")
                return True
            except OSError as e:
                print(f"Error removing directory {directory}: {e}")
                return False
        return False
    
    def start(self):
        """Start monitoring"""
        if not self.is_running:
            try:
                self.observer.start()
                self.is_running = True
                print("File monitoring started")
                return True
            except OSError as e:
                print(f"Error starting file monitor: {e}")
                return False
        return False
    
    def stop(self):
        """Stop monitoring"""
        if self.is_running:
            try:
                self.observer.stop()
                self.observer.join()
                self.is_running = False
                print("File monitoring stopped")
                return True
            except OSError as e:
                print(f"Error stopping file monitor: {e}")
                return False
        return False
    
    def get_monitored_directories(self):
        """Get list of currently monitored directories"""
        return list(self.monitored_paths)
    
    def is_monitoring(self, directory):
        """Check if a directory is being monitored"""
        return directory in self.monitored_paths 