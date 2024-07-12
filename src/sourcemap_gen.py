import http.server
import socketserver
import os
import json

PORT = 3669
SOURCEMAP_FILE_PATH = "sourcemap.json"
ROJO_PROJECT_FILE_PATH = "default.project.json"

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def get_value_from_path(nested_dict, path_keys):
    path_keys = path_keys.copy()

    for value in nested_dict["children"]:
        if len(path_keys) <= 0:
            return nested_dict
    
        if value["name"] != path_keys[0]:
            continue

        path_keys.pop(0)
        
        return get_value_from_path(value, path_keys)
        

def get_path_str_from_path_list(path_keys):
    path_str = ""

    for key in path_keys:
        if path_str == "":
            path_str = key
            continue
        path_str = path_str + "/" + key
    
    return path_str

#def get_path_for_item(itemName):
    # identifies the path of the item within the directory based on the ROJO_PROJECT_FILE_PATH

def add_reference_from_pf(tree: dict, sourcemap: dict, referenceCache, pathKeys=[]):

    for key, value in tree.items():

        newPathKeys = pathKeys.copy()

        if key == "$path":
            inSourcemap = get_value_from_path(sourcemap, newPathKeys)
            #print("PathKeys:", pathKeys)
            #print("inSourecmap:", inSourcemap)
            #print("FilePaths:", value)
            if inSourcemap == None:
                print(f"{bcolors.WARNING}WARN{bcolors.ENDC} FilePaths write fail, could not find placement in sourcemap for Pathkey: {newPathKeys}")
                continue
            else:
                print(f"Loaded path for Pathkey: {newPathKeys}")

            filePath = [get_path_str_from_path_list(str(value).split("/"))]

            referenceCache.append([newPathKeys, filePath])

            inSourcemap["filePaths"] = filePath
            continue

        if key.startswith("$"):
            continue

        newPathKeys.append(key)
        
        add_reference_from_pf(value, sourcemap, referenceCache, newPathKeys)
        

def add_reference_for_scripts(sourcemap: dict, referenceCache, pathKeys=[], upperPathKeyIndex=0):
    for value in sourcemap["children"]:
        newPathKeys = pathKeys.copy()
        newPathKeys.append(value["name"])
            
        if "filePaths" in value:
            # recursive call to add_reference_for_scripts(...)
            # mark the filePath index in the pathKeys
            for pair in referenceCache:
                if pair[0] != newPathKeys:
                    continue
                keys = pair[1]
            
            filePath = get_path_str_from_path_list(keys)
            hasLuaExtensionInit = os.path.exists(filePath + "/init.lua")
            hasLuauExtensionInit = os.path.exists(filePath + "/init.luau")
            if os.path.isdir(filePath):
                if hasLuaExtensionInit:
                    if hasLuauExtensionInit:
                        print(f"{bcolors.WARNING}WARN{bcolors.ENDC} Name conflict: the name {pathKeys[-1]} used for init.lua and init.luau, fallback to init.lua")

                    value["filePaths"] = [filePath + "/init.lua"]
                elif hasLuauExtensionInit:
                    value["filePaths"] = [filePath + "/init.luau"]

            add_reference_for_scripts(value, referenceCache, newPathKeys, len(pathKeys))
            continue

        # we only want scripts
        className = value["className"]
        if className != "ModuleScript" and className != "Script" and className != "LocalScript":
            add_reference_for_scripts(value, referenceCache, newPathKeys, upperPathKeyIndex)
            continue

        # if an ancestry filePath is marked
        if upperPathKeyIndex:
            startingKeys = pathKeys[:upperPathKeyIndex+1]
            for pair in referenceCache:
                if pair[0] != startingKeys:
                    continue
                startingKeysNew = pair[1]

            filePath = get_path_str_from_path_list(startingKeysNew + pathKeys[upperPathKeyIndex+1:] + [value["name"]])
            hasLuaExtension = os.path.exists(filePath + ".lua")
            hasLuauExtension = os.path.exists(filePath + ".luau")

            if hasLuaExtension:
                if hasLuauExtension:
                    print(f"{bcolors.WARNING}WARN{bcolors.ENDC} Name conflict: the name {pathKeys[-1]} used for .lua and .luau, fallback to .lua")
                value["filePaths"] = [filePath + ".lua"]
            elif hasLuauExtension:
                value["filePaths"] = [filePath + ".luau"]
            elif os.path.isdir(filePath):
                # find init file
                hasLuaExtensionInit = os.path.exists(filePath + "/init.lua")
                hasLuauExtensionInit = os.path.exists(filePath + "/init.luau")

                if hasLuaExtensionInit:
                    if hasLuauExtensionInit:
                        print(f"{bcolors.WARNING}WARN{bcolors.ENDC} Name conflict: the name {pathKeys[-1]} used for init.lua and init.luau, fallback to init.lua")

                    value["filePaths"] = [filePath + "/init.lua"]
                elif hasLuauExtensionInit:
                    value["filePaths"] = [filePath + "/init.luau"]
                else:
                    projectFilePath = filePath + "/default.project.json"

                    if not os.path.exists(projectFilePath):
                        print(f"{bcolors.WARNING}WARN{bcolors.ENDC} No project file found for path: {projectFilePath}")
                        continue

                    with open(projectFilePath, "r") as file:
                        projectFile = json.loads(file.read())

                        folderPath = projectFile["tree"]["$path"]
                        newPath = filePath + "/" + folderPath
                        folderHasLuaExtensionInit = os.path.exists(newPath + "/init.lua")
                        folderHasLuauExtensionInit = os.path.exists(newPath + "/init.luau")

                        if folderHasLuaExtensionInit:
                            if folderHasLuauExtensionInit:
                                print(f"{bcolors.WARNING}WARN{bcolors.ENDC} Name conflict: the name {pathKeys[-1]} used for init.lua and init.luau, fallback to init.lua")

                            value["filePaths"] = [newPath + "/init.lua"]
                        elif folderHasLuauExtensionInit:
                            value["filePaths"] = [newPath + "/init.luau"]

            add_reference_for_scripts(value, referenceCache, newPathKeys, upperPathKeyIndex)
            

def generate_sourcemap(sourcemap: str):
    # loads into json
    with open(ROJO_PROJECT_FILE_PATH, "r") as file:
        projectFile = json.loads(file.read())

    # payload

    sourcemapFile = json.loads(sourcemap)

    referenceCache = []

    add_reference_from_pf(projectFile["tree"], sourcemapFile, referenceCache)
    add_reference_for_scripts(sourcemapFile, referenceCache)

    with open(SOURCEMAP_FILE_PATH, "w") as file:
        file.write(json.dumps(sourcemapFile, sort_keys=False, separators=(",", ":")))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"GET request received from {self.client_address}: {self}")
        return super().do_GET()
    def do_POST(self):
        print(f"POST request received from {self.client_address}")
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        #print(f"Data received in POST request: {post_data.decode('utf-8')}")

        # return a response
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"POST request received")

        generate_sourcemap(post_data.decode("utf-8"))
        
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Listening to Port: {PORT}")
    httpd.serve_forever()