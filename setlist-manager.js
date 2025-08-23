// M4L uses some janky old ES so no let/const/modern features allowed

// Declare inlets and outlets
inlets = 2;
outlets = 3; // outlet 0 for data, outlet 1 for interlude, outlet 2 for status/errors

// Outlet index variables for clarity
var SONG_OUTLET = 0;
var INTERLUDE_OUTLET = 1;
var STATUS_OUTLET = 2;

var storedPath = "";
var setlistData = null;
var basePath = null; // Loaded from config.json
var serverPort = null; // Loaded from config.json

// Consts, but there's no const
var NEXT = "next";
var PREV = "prev";

function loadjson(filepath) {
    try {
        var absolutePath = filepath;
        // If it's just a filename (no path separators), look in the same directory as this JS file
        if (filepath.indexOf('/') === -1 && filepath.indexOf('\\') === -1) {
            try {
                var jsFilePath = this.patcher.filepath;
                var jsDir = jsFilePath.substring(0, jsFilePath.lastIndexOf('/'));
                absolutePath = jsDir + "/" + filepath;
            } catch (e) {
                outlet(STATUS_OUTLET, "couldn't get patcher path: " + e.message);
            }
        }
        // Use Max's File object to read the file
        var file = new File(absolutePath, "read");
        if (!file.isopen) {
            outlet(STATUS_OUTLET, "error: couldn't open file - " + absolutePath);
            return;
        }
        var fileContent = "";
        var line;
        while ((line = file.readline()) !== null) {
            fileContent += line;
        }
        file.close();
        if (fileContent === "") {
            outlet(STATUS_OUTLET, "error: file is empty - " + absolutePath);
            return;
        }
        setlistData = JSON.parse(fileContent);
        outlet(STATUS_OUTLET, "loaded: " + absolutePath);
        return setlistData;
    } catch (e) {
        outlet(STATUS_OUTLET, "error: " + e.message);
    }
}

// Load config.json for basePath and serverPort
function loadconfig() {
    try {
        var jsFilePath = this.patcher.filepath;
        var jsDir = jsFilePath.substring(0, jsFilePath.lastIndexOf('/'));
        var configPath = jsDir + "/config.json";
        var file = new File(configPath, "read");
        if (!file.isopen) {
            outlet(STATUS_OUTLET, "error: couldn't open config.json - " + configPath);
            return;
        }
        var fileContent = "";
        var line;
        while ((line = file.readline()) !== null) {
            fileContent += line;
        }
        file.close();
        if (fileContent === "") {
            outlet(STATUS_OUTLET, "error: config.json is empty - " + configPath);
            return;
        }
        var config = JSON.parse(fileContent);
        basePath = config.basePath !== undefined ? config.basePath : null;
        serverPort = config.serverPort !== undefined ? config.serverPort : null;
        if (serverPort === null) {
            outlet(STATUS_OUTLET, "error: no valid serverPort specified in config.json");
        } else {
            setport(serverPort);
        }
    outlet(STATUS_OUTLET, "config loaded: " + configPath);
        return config;
    } catch (e) {
        outlet(STATUS_OUTLET, "error loading config: " + e.message);
    }
}

// You can't get the live set filepath directly (wtf) so we get the name of the .als
// N.B - if you have a set with two .als's that have the same name, you're fucked
function getCurrentSet() {
    try {
        const liveSet = new LiveAPI("live_set");
        return liveSet.get("name");
    } catch (e) {
    outlet(STATUS_OUTLET, "error getting current set: " + e.message);
        return null;
    }
}

function path(_, filepath) {
    // Always load config first
    loadconfig();
    var currentSetName = getCurrentSet();
    storedPath = filepath;
    var data = loadjson(filepath);
    if (data && currentSetName) {
        var currentIndex = findCurrentSetIndex(currentSetName, data);
        if (currentIndex !== -1) {
            post("current set index: " + currentIndex);
            var nextIndex = currentIndex + 1;
            if (nextIndex >= data.sets.length) {
                outlet(SONG_OUTLET, ["text", "NO NEXT SET"])
            }
            var nextSet = data.sets[nextIndex];
            var nextSetName = extractSetName(nextSet.path);
            outlet(SONG_OUTLET, ["text", nextSetName]);
            // Send current set's interlude (if present) to interlude outlet
            var currentSet = data.sets[currentIndex];
            if (currentSet.interlude) {
                outlet(INTERLUDE_OUTLET, ["text", currentSet.interlude]);
            }
        } else {
            post("current set not found in setlist");
            outlet(STATUS_OUTLET, "warning: current set not found in setlist");
        }
    }
}

// M4L doesn't support getting the filepath of the current set so you have to just string match
// on name.
// ** DON'T EVER USE DUPLICATE SET NAMES WITH THIS SYSTEM **
function findCurrentSetIndex(currentSetName, setlistData) {
    if (!setlistData || !setlistData.sets || !currentSetName) {
        return -1;
    }
    
    for (var i = 0; i < setlistData.sets.length; i++) {
        var setPath = setlistData.sets[i].path;
        
        // Use indexOf instead of includes for M4L compatibility
        if (setPath.indexOf(currentSetName) !== -1) {
            return i;
        }
    }
    
    return -1; // Not found
}

// Helper to resolve set path using basePath from config.json
function resolveSetPath(path) {
    if (!basePath || path.indexOf('/') === 0 || path.indexOf(':') !== -1) {
        return path;
    }
    var sep = basePath.charAt(basePath.length - 1) === '/' || basePath.charAt(basePath.length - 1) === '\\' ? '' : '/';
    return basePath + sep + path;
}

// Function to send HTTP request to local server
function sendToServer(setPath, setIndex) {
    post("SENDING")
    try {
        // Create the request data
        var requestData = {
            "action": "load_set",
            "path": resolveSetPath(setPath),
            "index": setIndex
        };
        
        // Convert to JSON string
        var jsonData = JSON.stringify(requestData);
        
        // Use Max's http object to send POST request
        var httpRequest = new XMLHttpRequest();
        var url = "http://localhost:" + serverPort + "/load-set";
        
        httpRequest.open("POST", url, true);
        httpRequest.setRequestHeader("Content-Type", "application/json");
        
        httpRequest.onreadystatechange = function() {
            if (httpRequest.readyState === 4) {
                if (httpRequest.status === 200) {
                    outlet(STATUS_OUTLET, "server request successful: " + httpRequest.responseText);
                    outlet(STATUS_OUTLET, ["server_response", "success", setPath]);
                } else {
                    outlet(STATUS_OUTLET, "server request failed: " + httpRequest.status + " " + httpRequest.statusText);
                    outlet(STATUS_OUTLET, ["server_response", "error", httpRequest.status]);
                }
            }
        };
        
        httpRequest.send(jsonData);
        outlet(STATUS_OUTLET, "sending request to server: " + url);
        
    } catch (e) {
        outlet(STATUS_OUTLET, "error sending to server: " + e.message);
        outlet(SONG_OUTLET, "text", "FAILURE LOADING NEXT SET")
    }
}

// Function to navigate to next/previous set
function navigate(direction) {
    if (!setlistData) {
        outlet(STATUS_OUTLET, "error: no setlist loaded");
        return;
    }
    
    var currentSetName = currentSet();
    var currentIndex = findCurrentSetIndex(currentSetName, setlistData);
    
    if (currentIndex === -1) {
        outlet(STATUS_OUTLET, "error: current set not found in setlist");
        return;
    }
    
    var newIndex;
    if (direction === NEXT) {
        newIndex = (currentIndex + 1) % setlistData.sets.length;
    } else if (direction === PREV) {
        newIndex = (currentIndex - 1 + setlistData.sets.length) % setlistData.sets.length;
    } else {
        outlet(STATUS_OUTLET, "error: invalid direction. use 'next' or 'prev'");
        return;
    }
    
    var nextSetPath = setlistData.sets[newIndex].path;
    
    outlet(STATUS_OUTLET, "navigating to: " + nextSetPath + " (index " + newIndex + ")");
    
    // Send to server instead of direct loading
    sendToServer(nextSetPath, newIndex);
}

// Message handlers
function next() {
    navigate(NEXT);
}

function prev() {
    navigate(PREV);
}

// Manual server port setting
function setport(port) {
    serverPort = port;
    outlet(STATUS_OUTLET, "server port manually set to: " + serverPort);
}

// Helper function to extract set name from file path
// Works with both forward and back slashes, removes file extension
// And again, can't use lastIndexOf and similar things because M4L
// uses some ancient ES interpreter
function extractSetName(filePath) {
    if (!filePath) {
        return "Unknown";
    }
    
    var filename = filePath;
    
    // Find the last slash (either / or \) manually
    var lastSlashIndex = -1;
    for (var i = filePath.length - 1; i >= 0; i--) {
        if (filePath.charAt(i) === '/' || filePath.charAt(i) === '\\') {
            lastSlashIndex = i;
            break;
        }
    }
    
    // Extract filename (everything after the last slash)
    if (lastSlashIndex !== -1) {
        filename = filePath.substring(lastSlashIndex + 1);
    }
    
    // Remove file extension (everything after the last dot) manually
    var lastDotIndex = -1;
    for (var i = filename.length - 1; i >= 0; i--) {
        if (filename.charAt(i) === '.') {
            lastDotIndex = i;
            break;
        }
    }
    
    var nameWithoutExtension = filename;
    if (lastDotIndex !== -1) {
        nameWithoutExtension = filename.substring(0, lastDotIndex);
    }
    
    return nameWithoutExtension;
}