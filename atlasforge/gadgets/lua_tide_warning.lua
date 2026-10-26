--------------------------------------------------------------------------------
-- Atlas Tide Warning (map gadget, Atlas Map Forge)
-- Shows when the ZK lava (map_lava.lua, GameRulesParam "lavaLevel") rises or falls
-- and marks the fords that flood at high tide.
--------------------------------------------------------------------------------
function gadget:GetInfo()
	return {
		name    = "Atlas Tide Warning",
		desc    = "Countdown and ford markers for lava tides (map gadget)",
		author  = "Atlas Map Forge",
		layer   = 10,
		enabled = true,
	}
end

if gadgetHandler:IsSyncedCode() then
	return
end

local TIDE_FILE = "mapconfig/atlas_tide.lua"
local LAVA_FILE = "mapconfig/lava_config.lua"

local conf, rhym
local lastLevel
local phase = "start"
local nextChange
local holdHigh = false

local spGetGameRulesParam = Spring.GetGameRulesParam
local spGetGameFrame = Spring.GetGameFrame
local abs, floor = math.abs, math.floor

function gadget:Initialize()
	if not (VFS.FileExists(TIDE_FILE) and VFS.FileExists(LAVA_FILE)) then
		gadgetHandler:RemoveGadget(self)
		return
	end
	conf = VFS.Include(TIDE_FILE)
	local lava = VFS.Include(LAVA_FILE)
	rhym = lava and lava.tideRhym
	if not rhym or #rhym == 0 then
		gadgetHandler:RemoveGadget(self)
		return
	end
	Spring.Echo("Atlas Tide Warning: " .. #conf.fords .. " fords, flood level " .. conf.floodLevel)
end

local function nearestTide(level)
	local best, bi = math.huge, 1
	for i = 1, #rhym do
		local d = abs((rhym[i].target or 0) - level)
		if d < best then
			best, bi = d, i
		end
	end
	return rhym[bi]
end

function gadget:GameFrame(f)
	local lv = spGetGameRulesParam("lavaLevel")
	if not lv or lv < -1000 then
		return
	end
	if lastLevel then
		local d = lv - lastLevel
		if d > 0.005 then
			phase = "rise"
		elseif d < -0.005 then
			phase = "fall"
		elseif phase ~= "hold" then
			phase = "hold"
			local t = nearestTide(lv)
			nextChange = f + (t.period or 0) * 30
			holdHigh = lv > conf.floodLevel * 0.5
		end
	end
	lastLevel = lv
end

local function fmt(frames)
	local s = math.max(0, floor(frames / 30 + 0.5))
	return string.format("%d:%02d", floor(s / 60), s % 60)
end

local function state()
	local f = spGetGameFrame()
	if phase == "rise" then
		return "rise", nil
	elseif phase == "fall" then
		return "fall", nil
	elseif phase == "hold" and nextChange then
		local rem = nextChange - f
		if holdHigh then
			return "flood", rem
		elseif rem <= conf.warnSeconds * 30 then
			return "warn", rem
		end
		return "safe", rem
	end
	return nil, nil
end

function gadget:DrawScreen()
	local st, rem = state()
	if not st then
		return
	end
	local vsx, vsy = gl.GetViewSizes()
	local blink = (floor(Spring.GetGameSeconds() * 2) % 2 == 0)
	local txt
	if st == "safe" then
		txt = "\255\255\220\120Lava low tide  \255\255\255\255High tide in " .. fmt(rem)
	elseif st == "warn" then
		txt = (blink and "\255\255\140\0" or "\255\255\220\120") .. "LAVA RISING IN " .. fmt(rem) .. "  -  leave the fords!"
	elseif st == "rise" then
		txt = "\255\255\60\30LAVA RISING  -  fords are flooding"
	elseif st == "flood" then
		txt = "\255\255\60\30LAVA HIGH TIDE  \255\255\255\255Fords closed, low tide in " .. fmt(rem)
	elseif st == "fall" then
		txt = "\255\255\200\60Lava falling"
	end
	gl.Text(txt, vsx * 0.5, vsy - 150, 20, "co")
end

function gadget:DrawWorldPreUnit()
	local st = state()
	if not st or not gl.DrawGroundQuad then
		return
	end
	local t = Spring.GetGameSeconds()
	local a
	if st == "safe" then
		gl.Color(1.0, 0.85, 0.2, 0.08)
	elseif st == "warn" then
		a = 0.18 + 0.14 * math.sin(t * 6)
		gl.Color(1.0, 0.45, 0.0, a)
	elseif st == "rise" or st == "flood" then
		gl.Color(1.0, 0.15, 0.05, 0.25)
	else
		gl.Color(1.0, 0.6, 0.1, 0.15)
	end
	gl.DepthTest(false)
	for i = 1, #conf.fords do
		local q = conf.fords[i]
		pcall(gl.DrawGroundQuad, q[1], q[2], q[3], q[4])
	end
	gl.Color(1, 1, 1, 1)
end
