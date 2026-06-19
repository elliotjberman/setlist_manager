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
    "basePath": "/Users/you/Music/AbletonSets",
    "serverPort": 8000
}
```

- **sets**: List of objects, each with a `"path"` to an Ableton `.als` file. Paths can be absolute or relative.
- **serverPort**: Port number for the local server. The client and server side both read this value.
- **udpPort** (optional): UDP fire-and-forget port for the M4L device. Defaults to `serverPort`.
- **basePath** (optional): If present, all relative `"path"` entries will be resolved relative to this directory.

## Code Structure

- The Max for Live (M4L) device uses JavaScript, but only supports some insane version of ECMAScript (shit/non-existent standard library, no `let`, `const`, etc).
- M4L scripts also can't launch new Ableton sets themselves, or get the path of the current set running (???).
- To work around this, a Python server (`server.py`) runs locally and handles file operations and launching sets. The M4L JS client sends fire-and-forget UDP messages to this server. HTTP remains available for `/status` and debugging.
- UDP-triggered opens wait one second by default before asking Ableton to load the next set. Override with `SETLIST_UDP_OPEN_DELAY=0` if you need the old immediate behavior.
- Platform-specific behavior is isolated behind `platform_adapters.py`.
- Windows-specific code lives in `windows/`, including the Win32 save dialog handler and launcher.
- macOS-specific code lives in `macos/`, including an on-demand save prompt handler that sends Ableton's "Don't Save" keyboard shortcut after opening the next set.
- Path/setlist validation and other utilities are handled in Python scripts (like `validate_paths.py`).

## Running the Server

Install shared dependencies:

```sh
python -m pip install -r requirements.txt
```

On macOS, you can run:

```sh
./macos/server_start.command
```

The macOS save prompt handler uses Accessibility automation. If the prompt is not dismissed automatically, grant Accessibility permission to the app running the server in System Settings > Privacy & Security > Accessibility.

Ableton does not always expose its save prompt as a normal Accessibility dialog on macOS, so after a server-driven set open the handler also sends the prompt's "Don't Save" keyboard shortcut.

On Windows, run `windows/server_start.bat`. It installs the shared dependencies plus `windows/requirements.txt`.

The server also exposes `GET /status` for dashboards. It returns JSON with `ok`, `serverPort`, `udpPort`, `basePath`, `sets`, `current_index`, and `current_path`. If `setlist.json` is missing, the server falls back to port `8000` so `/status` can report the problem cleanly.

**Tips:**
- Make sure all paths exist; use `validate_paths.py` to check.
- If you use VS Code, you can add the [settings.json](./.vscode/settings.json) extension setup—this will show you in the status bar if there's something wrong with your setlist file (bad syntax or missing files)
