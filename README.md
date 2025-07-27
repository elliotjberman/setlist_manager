# setlist_manager
VS Live Set Navigation in M4L + Ableton

## Ableton Usage
You can trigger the next set by either clicking the button itself, or sending MIDI note 0 through the device's MIDI input

## Setting up `setlist.json`

Your `setlist.json` file defines the sets and server configuration. Place it in the same directory as the scripts.

Example structure:
```json
{
    "sets": [
        { "path": "song1/song1.als" },
        { "path": "song2/song2.als" }
    ],
    "basePath": "C:/AbletonSets",
    "serverPort": 8000
}
```

- **sets**: List of objects, each with a `"path"` to an Ableton `.als` file. Paths can be absolute or relative.
- **serverPort**: Port number for the local server. The client and server side both read this value.
- **basePath** (optional): If present, all relative `"path"` entries will be resolved relative to this directory.

## Code Structure

- The Max for Live (M4L) device uses JavaScript, but only supports some insane version of ECMAScript (shit/non-existent standard library, no `let`, `const`, etc).
- M4L scripts also can't launch new Ableton sets themselves, or get the path of the current set running (???).
- To work around this, a Python server (`server.py`) runs locally and handles file operations and launching sets. The M4L JS client communicates with this server over HTTP.
- Path/setlist validation and other utilities are handled in Python scripts (like `validate_paths.py`).

**Tips:**
- Make sure all paths exist; use `validate_paths.py` to check.
- If you use VS Code, you can add the [settings.json](./.vscode/settings.json) extension setup—this will show you in the status bar if there's something wrong with your setlist file (bad syntax or missing files)