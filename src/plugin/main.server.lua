--!nonstrict
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Selection = game:GetService("Selection")

assert(plugin, "This code must run inside of a plugin")
local toolbar = plugin:CreateToolbar("LLS Datamodel") :: PluginToolbar

local rblxgui = require(script.Parent.lib.rblxgui.initialize)
local gui = rblxgui(plugin, "llc")
local SETTINGS = {
	port = 3669
}

local button = toolbar:CreateButton(
	"Luau Language Server Setup",
	"Toggle Menu",
	"rbxassetid://11115506617",
	"Luau Language Server"
) :: PluginToolbarButton
button.ClickableWhenViewportHidden = true

local widget = gui.PluginWidget.new({
	ID = "Luau Language Server Datamodel",
	Enabled = false,
	Dockstate = Enum.InitialDockState.Float
})

local mainPage = gui.Page.new({
	Name = "Main",
	TitlebarMenu = widget.TitlebarMenu,
	Open = true
})

local mainframe = gui.ScrollingFrame.new(nil, mainPage.Content)
-- sets mainframe as the main element(everything will go here by default unless you specify a parent)
mainframe:SetMain()

gui.Textbox.new {
	Text = "Connect to begin synchonizing datamodel information"
}

local connectButton = gui.ToggleableButton.new({
	Text = "Connect",
})
gui.Labeled.new({
	Text = `<b>Connect to</b>: http://localhost:{SETTINGS.port}`,
	Object = connectButton
})

local connected = false

local connections = {}

local INCLUDED_SERVICES = {
	game:GetService("Workspace"),
	game:GetService("Players"),
	game:GetService("Lighting"),
	game:GetService("ReplicatedFirst"),
	game:GetService("ReplicatedStorage"),
	game:GetService("ServerScriptService"),
	game:GetService("StarterGui"),
	game:GetService("StarterPlayer"),
	game:GetService("SoundService"),
	game:GetService("Chat"),
	game:GetService("LocalizationService"),
}

type EncodedInstance = {
	name: string,
	className: string,
	children: { EncodedInstance },
}

local syncButton

local function filterServices(child: Instance): boolean
	return not not table.find(INCLUDED_SERVICES, child)
end

local function encodeInstance(instance: Instance, childFilter: ((Instance) -> boolean)?, instances: {}): EncodedInstance
	local encoded = {}
	encoded.name = instance.Name
	encoded.className = instance.ClassName
	encoded.children = {}

	local nameCache = {}

	for _, child in instance:GetChildren() do
		if childFilter and not childFilter(child) then
			continue
		end

		local childEncoded = encodeInstance(child, nil, instances)
		table.insert(encoded.children, childEncoded)
	end

	table.insert(instances, instance)

	return encoded
end

local function getSize(s: string)
	local size = s:len()
	return math.round((size/1000000)*1000)/1000 .. "MB"
end

local function sendDataModelInfo()
	local instances = {}
	local body = HttpService:JSONEncode(encodeInstance(game, filterServices, instances))

	local size = getSize(body)

	local success, result = pcall(HttpService.RequestAsync, HttpService, {
		Method = "POST",
		Url = string.format("http://localhost:%s", SETTINGS.port),
		Headers = {
			["Content-Type"] = "application/json",
		},
		Body = body,
	})
	return success, result, size, instances
end

local requestSend = false
local lastRequestSend = 0

local function makeConnection()
	local success, result, size, instances = sendDataModelInfo()

	if not success or not result then
		warn(`LLS: Couldn't connect to local server:\n Stat: port={SETTINGS.port}, size={size}\n{result}`)
		connected = false
		connectButton.Textbox.Text = "Connect"
	else
		print("LLS: Connected to local server")
		print(`LLS: Payload with size of {size} was successfully sent`)
		connected = true

		for _, instance in INCLUDED_SERVICES do
			table.insert(connections, instance.DescendantAdded:Connect(function() 
				requestSend = true
			end))
			table.insert(connections, instance.DescendantRemoving:Connect(function() 
				requestSend = true
			end))
		end

		connectButton.Textbox.Text = "Disconnect"

		print(`LLS: Established {#connections} connections`)
	end
	
	connectButton:ToggleEnable()
end

connectButton:Clicked(function() 
	connected = not connected
	connectButton:SetValue(connected)

	lastRequestSend = 0
	requestSend = false

	if connected then
		connectButton:ToggleDisable()
		makeConnection()
	else
		for _, connection in connections do
			connection:Disconnect()
		end
		table.clear(connections)
		connectButton.Textbox.Text = "Connect"
		print("LLS: Disconnected")
	end
end)

local settingsPage = gui.Page.new({
	Name = "Settings",
	TitlebarMenu = widget.TitlebarMenu,
	Open = false
})

button.Click:Connect(function() 
	widget.Content.Enabled = not widget.Content.Enabled
end)

RunService.Heartbeat:Connect(function() 
	local nowClock = os.clock() 
	if connected and nowClock - lastRequestSend > 6 and requestSend then
		requestSend = false
		lastRequestSend = nowClock
		local success, result, size, instances = sendDataModelInfo()
		print(`LLS: Payload with size of {size} was successfully sent`)
	end
end)

local selectionConnections = {}

Selection.SelectionChanged:Connect(function()
	local selections = Selection:Get()

	for selection, connection in selectionConnections do
		if not table.find(selections, selection) then
			local index = table.find(selectionConnections, selection)
			if index then table.remove(selectionConnections, index) end
		end
	end
	for _, selection in selections do
		if not selectionConnections[selection] then
			selectionConnections[selection] = selection:GetPropertyChangedSignal("Name"):Connect(function() 
				requestSend = true
			end)
		end
	end
end)