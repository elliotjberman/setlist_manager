// M4L uses some janky old ES so no let/const/modern features allowed

// Declare inlets and outlets
inlets = 2;
outlets = 2; // outlet 0 for data, outlet 1 for status/errors

var storedPath = "";
var setlistData = null;
var basePath = null; // Store basePath if present
var serverPort = null;
var udpPort = null;
var udpSender = null;
var udpSenderPort = null;
var SCRIPT_VERSION = "udp-fire-and-forget-2026-06-18";

post("setlist-manager.js loaded: " + SCRIPT_VERSION + "\n");

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
        var file = new File(absolutePath, "read");
        
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
        // Store basePath if present
        basePath = setlistData.basePath !== undefined ? setlistData.basePath : null;

        // Extract server port - required
        if (setlistData.serverPort === undefined) {
            outlet(1, "error: no valid serverPort specified in JSON");
            return;
        }
        setport(setlistData.serverPort);
        if (setlistData.udpPort !== undefined) {
            setudpport(setlistData.udpPort);
        } else {
            setudpport(setlistData.serverPort);
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
                outlet(0, ["text", "NO NEXT SET"]);
                return;
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
        var liveSet = new LiveAPI("live_set");
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

function ensureUdpSender() {
    if (udpPort === null) {
        outlet(1, "error: no UDP port configured");
        return null;
    }

    if (udpSender && udpSender.valid && udpSenderPort === udpPort) {
        return udpSender;
    }

    try {
        udpSender = this.patcher.newdefault(20, 20, "udpsend", "127.0.0.1", udpPort);
        udpSender.hidden = 1;
        udpSender.ignoreclick = 1;
        udpSenderPort = udpPort;
        post("created udpsend 127.0.0.1:" + udpPort + "\n");
        return udpSender;
    } catch (e) {
        outlet(1, "error creating udpsend: " + e.message);
        return null;
    }
}

function sendUdpRawBytes(payload) {
    var sender = ensureUdpSender();
    if (!sender) {
        return false;
    }

    var args = ["rawbytes"];
    for (var i = 0; i < payload.length; i++) {
        var code = payload.charCodeAt(i);
        if (code > 255) {
            throw new Error("UDP payload contains non-byte character at " + i);
        }
        args[args.length] = code;
    }

    sender.message.apply(sender, args);
    return true;
}

// Function to send a UDP fire-and-forget request to the local server.
function sendToServer(setIndex) {
    post("SENDING UDP\n");
    try {
        var requestData = {
            "action": "load_index",
            "index": setIndex
        };
        
        var jsonData = JSON.stringify(requestData);

        if (!sendUdpRawBytes(jsonData)) {
            throw new Error("UDP send failed");
        }

        outlet(1, "udp request sent to server: 127.0.0.1:" + udpPort + " index " + setIndex);
        
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
    
    sendToServer(newIndex);
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

function setudpport(port) {
    udpPort = port;
    outlet(1, "udp port manually set to: " + udpPort);
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
