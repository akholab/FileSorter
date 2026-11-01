# Smart File Indexer

A Python-based file indexing and organization system for Windows that intelligently categorizes and suggests file organization based on file types, content, and user preferences.

## Features

- **Smart File Categorization**: Automatically categorizes files based on extensions and content analysis
- **User-Friendly GUI**: Modern interface with drag-and-drop support and intuitive controls
- **Background Monitoring**: Runs in the background and provides non-intrusive notifications
- **Flexible Organization**: Suggests multiple organization options for each file
- **Persistent Indexing**: Maintains a database of file locations and organization decisions
- **Customizable Categories**: Easy to modify file categories and organization rules
- **Learns Your Habits**: After you move (or keep) the same kind of file the same way twice, that choice is suggested first. "Kind of file" means the same extension in the same watched folder. Undo takes the lesson back. Change the number with `learn_threshold` in the config file
- **Safe Moves**: Never overwrites a file (a clash becomes `name (2).ext`), waits until a download has finished, keeps Undo across restarts, and sends deleted files to the Recycle Bin

## Installation

1. **Clone or download the project files**
2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Starting the Application

**Option 1: Use the Launcher (Recommended)**
```bash
python launcher.py
```
This opens a launcher where you can choose between GUI and System Tray modes.

**Option 2: Direct Launch**
- GUI Mode: `python file_indexer.py`
- System Tray Mode: `python tray_indexer.py`

**Option 3: Windows Batch Files**
- Double-click `run.bat` to start the launcher
- Double-click `install.bat` to install dependencies

**Option 4: Hidden Launch (No Terminal Windows)**
- Double-click `run_hidden.bat` to start without any terminal windows
- Double-click `run_simple_hidden.bat` for a simple hidden launcher
- Double-click `start_hidden.bat` for the most minimal hidden start
- Double-click `FileManager.vbs` for a VBScript launcher (can be pinned to taskbar)

### Basic Workflow

1. **Scan Directories**: Click "Scan Directory" to select folders for indexing
2. **Review Suggestions**: The system will suggest organization options for each file
3. **Make Decisions**: Choose to move, keep, or skip files based on suggestions
4. **Background Operation**: The system continues monitoring and providing suggestions

### Features in Detail

#### Smart Categorization
The system automatically categorizes files into:
- **Documents**: PDFs, Word docs, text files, etc.
- **Images**: Photos, screenshots, graphics
- **Videos**: Movie files, recordings
- **Audio**: Music, podcasts, sound files
- **Archives**: Compressed files, backups
- **Code**: Programming files, scripts
- **Misc**: Other file types

#### Organization Suggestions
For each file, the system provides multiple options:
- Move to appropriate category folder
- Keep in current location
- Custom organization paths

#### Background Monitoring
- Runs silently in the background
- Shows notifications only when suggestions are available
- Non-intrusive popup notifications
- Configurable notification timing
- System tray mode for minimal distraction
- Real-time file system monitoring

#### Settings
Access settings to configure:
- Auto-sort behavior
- Notification delays
- File size thresholds
- Watch directories

## File Structure

```
FileManager/
├── launcher.py              # Application launcher
├── file_indexer.py          # Main GUI application
├── tray_indexer.py          # System tray application
├── file_monitor.py          # File monitoring module
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup script
├── LICENSE                  # MIT License
├── MANIFEST.in              # Package manifest
├── .gitignore               # Git ignore file
├── cleanup.bat              # Cleanup script
├── run.bat                  # Windows launcher script
├── run_hidden.bat           # Hidden launcher (no terminal)
├── run_simple_hidden.bat    # Simple hidden launcher
├── start_hidden.bat         # Minimal hidden start
├── FileManager.vbs          # VBScript launcher (taskbar-friendly)
├── install.bat              # Windows dependency installer
├── README.md                # This file
├── file_indexer_config.ini  # Configuration file (auto-generated)
└── file_index.json          # File index database (auto-generated)
```

## Configuration

The system automatically creates configuration files:
- `file_indexer_config.ini`: Application settings
- `file_index.json`: Database of indexed files and decisions

## Customization

### Adding New File Categories

Categories live in `rules.toml`, next to the app's other data files. The app writes it with the built-in categories the first time it starts. Edit it and restart the app:

```toml
[categories.taxes]
extensions = [".pdf", ".xlsx"]   # checked first, top category wins
keywords = ["invoice", "receipt"] # words in the file name
folders = ["Taxes"]               # where to suggest moving the file
```

If the file has a mistake, the app shows which line and uses the built-in categories until you fix it. Delete the file to get the defaults back.

### Preview Sorting

The **Preview Sorting** button lists every file in a folder with where it would go and why ("category: documents" or "your usual"). It never moves anything.

### Modifying Organization Rules

Update the `suggest_organization` function in `categorizer.py` to add custom logic for file organization.

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the application has read/write permissions to target directories
2. **Missing Dependencies**: Run `pip install -r requirements.txt` to install all required packages
3. **File Lock Issues**: Close any applications that might have files open

### Performance Tips

- Limit the number of directories being monitored
- Regularly clean up the index file if it becomes too large
- Use appropriate file size thresholds for your system

### Hidden Launch Options

If you prefer to run the application without any visible terminal windows:

1. **`run_hidden.bat`**: Full-featured hidden launcher with virtual environment support
2. **`run_simple_hidden.bat`**: Simple hidden launcher for basic usage
3. **`start_hidden.bat`**: Minimal hidden start script
4. **`FileManager.vbs`**: VBScript launcher that can be pinned to Windows taskbar

These options use `pythonw.exe` instead of `python.exe` to run without console windows. The application will still show GUI windows when needed, but no terminal/command prompt windows will appear.

## Development

### Setup Development Environment

1. **Clone the repository**
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Install in development mode**:
   ```bash
   pip install -e .
   ```

### Code Quality

- **Clean up cache files**: Run `cleanup.bat` to remove temporary files
- **Follow PEP 8**: Use consistent code formatting
- **Error handling**: Use specific exception types instead of generic `Exception`
- **Documentation**: Add docstrings to all functions and classes

### Building

To create a distributable package:
```bash
python setup.py sdist bdist_wheel
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License. 