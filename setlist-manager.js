// M4L uses some janky old ES so no let/const/modern features allowed

// Declare inlets and outlets
inlets = 2;
outlets = 2; // outlet 0 for data, outlet 1 for status/errors

var storedPath = "";
var setlistData = null;

// Consts, but there's no const
var NEXT = "next";
var PREV = "prev";

function loadjson(filepath) {
    try {
        var absolutePath = filepath;
        
        // If it's just a filename (no path separators), look in the same directory as this JS file
        if (filepath.indexOf('/') === -1 && filepath.indexOf('\\') === -1) {
            try {
                // Get the directory where this JS file is located
                var jsFilePath = this.patcher.filepath;
                var jsDir = jsFilePath.substring(0, jsFilePath.lastIndexOf('/'));
                absolutePath = jsDir + "/" + filepath;
            } catch (e) {
                outlet(1, "couldn't get patcher path: " + e.message);
            }
        }
        
        // Use Max's File object to read the file
        const file = new File(absolutePath, "read");
        
        if (!file.isopen) {
            outlet(1, "error: couldn't open file - " + absolutePath);
            return;
        }
        
        // Read the entire file
        var fileContent = "";
        var line;
        while ((line = file.readline()) !== null) {
            fileContent += line;
        }
        file.close();
        
        if (fileContent === "") {
            outlet(1, "error: file is empty - " + absolutePath);
            return;
        }
        
        // Parse JSON
        setlistData = JSON.parse(fileContent);
        
        // Extract server port - required
        if (setlistData.serverPort === undefined) {
            outlet(1, "error: no valid serverPort specified in JSON");
            return;
        }
        
        // Output success status
        outlet(1, "loaded: " + absolutePath);
        return setlistData;
        
    } catch (e) {
        outlet(1, "error: " + e.message);
    }
}

function path(_, filepath) {
    var currentSetName = currentSet();
    post("current set: " + currentSetName + "\n");
    
    storedPath = filepath;
    var data = loadjson(filepath);
    
    if (data && currentSetName) {
        var currentIndex = findCurrentSetIndex(currentSetName, data);
        if (currentIndex !== -1) {
            post("current set index: " + currentIndex);
            
            // Calculate next set index and get its name for display
            var nextIndex = currentIndex + 1;
            if (nextIndex >= data.sets.length) {
                outlet(0, ["text", "NO NEXT SET"])
            }

            var nextSetName = extractSetName(data.sets[nextIndex].path);
            outlet(0, ["text", nextSetName]);
        } else {
            post("current set not found in setlist");
            outlet(1, "warning: current set not found in setlist");
        }
    }
}

// You can't get the live set filepath directly (wtf) so we get the name of the .als
// N.B - if you have a set with two .als's that have the same name, you're fucked
function currentSet() {
    try {
        const liveSet = new LiveAPI("live_set");
        return liveSet.get("name");
    } catch (e) {
        outlet(1, "error getting current set: " + e.message);
        return null;
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

// Function to send HTTP request to local server
function sendToServer(setPath, setIndex) {
    post("SENDING")
    try {
        // Create the request data
        var requestData = {
            "action": "load_set",
            "path": setPath,
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
                    outlet(1, "server request successful: " + httpRequest.responseText);
                    outlet(1, ["server_response", "success", setPath]);
                } else {
                    outlet(1, "server request failed: " + httpRequest.status + " " + httpRequest.statusText);
                    outlet(1, ["server_response", "error", httpRequest.status]);
                }
            }
        };
        
        httpRequest.send(jsonData);
        outlet(1, "sending request to server: " + url);
        
    } catch (e) {
        outlet(1, "error sending to server: " + e.message);
        outlet(0, "text", "FAILURE LOADING NEXT SET")
    }
}

// Function to navigate to next/previous set
function navigate(direction) {
    if (!setlistData) {
        outlet(1, "error: no setlist loaded");
        return;
    }
    
    var currentSetName = currentSet();
    var currentIndex = findCurrentSetIndex(currentSetName, setlistData);
    
    if (currentIndex === -1) {
        outlet(1, "error: current set not found in setlist");
        return;
    }
    
    var newIndex;
    if (direction === NEXT) {
        newIndex = (currentIndex + 1) % setlistData.sets.length;
    } else if (direction === PREV) {
        newIndex = (currentIndex - 1 + setlistData.sets.length) % setlistData.sets.length;
    } else {
        outlet(1, "error: invalid direction. use 'next' or 'prev'");
        return;
    }
    
    var nextSetPath = setlistData.sets[newIndex].path;
    
    outlet(1, "navigating to: " + nextSetPath + " (index " + newIndex + ")");
    
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
    outlet(1, "server port manually set to: " + serverPort);
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