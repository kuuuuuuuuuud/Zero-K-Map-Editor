--------------------------------------------------------------------------------
-- Atlas Eruption (map gadget, Atlas Map Forge)
-- Follows the ZK lava tides (GameRulesParam "lavaLevel"): while the lava rises or stays high, the volcano
-- throws lava bombs. Shows a countdown and marks the causeways that flood.
-- Settings: mapconfig/atlas_eruption.lua, tides: mapconfig/lava_config.lua
--------------------------------------------------------------------------------
function gadget:GetInfo()
	return {
		name    = "Atlas Eruption",
		desc    = "Volcano eruptions with lava bombs, countdown and causeway markers (map gadget)",
		author  = "Atlas Map Forge",
		layer   = 10,
		enabled = true,
	}
end

local CONF_FILE = "mapconfig/atlas_eruption.lua"
local LAVA_FILE = "mapconfig/lava_config.lua"
if not (VFS.FileExists(CONF_FILE) and VFS.FileExists(LAVA_FILE)) then
	return
end
local conf = VFS.Include(CONF_FILE)
local lavaConf = VFS.Include(LAVA_FILE)
local rhym = lavaConf and lavaConf.tideRhym or {}

local spGetGameRulesParam = Spring.GetGameRulesParam
local abs, floor, sqrt, cos, sin, pi = math.abs, math.floor, math.sqrt, math.cos, math.sin, math.pi
local CX, CZ = conf.center[1], conf.center[2]

-- shared tide state machine (runs in synced and unsynced)
local lastLevel, phase, nextChange, holdHigh = nil, "start", nil, false
local function nearestTide(level)
	local best, bi = math.huge, 1
	for i = 1, #rhym do
		local d = abs((rhym[i].target or 0) - level)
		if d < best then best, bi = d, i end
	end
	return rhym[bi] or { period = 0 }
end
local function TrackTide(f)
	local lv = spGetGameRulesParam("lavaLevel")
	if not lv or lv < -1000 then return nil end
	if lastLevel then
		local d = lv - lastLevel
		if d > 0.005 then
			phase = "rise"
		elseif d < -0.005 then
			phase = "fall"
		elseif phase ~= "hold" then
			phase = "hold"
			nextChange = f + (nearestTide(lv).period or 0) * 30
			holdHigh = lv > conf.floodLevel * 0.5
		end
	end
	lastLevel = lv
	return lv
end
local function State(f)
	if phase == "rise" then return "rise", nil end
	if phase == "fall" then return "fall", nil end
	if phase == "hold" and nextChange then
		local rem = nextChange - f
		if holdHigh then return "flood", rem end
		if rem <= conf.warnSeconds * 30 then return "warn", rem end
		return "calm", rem
	end
	return nil, nil
end

--------------------------------------------------------------------------------
if gadgetHandler:IsSyncedCode() then
--------------------------------------------------------------------------------

local canFly = {}
local pending = {}
local bombAcc = 0
local spSpawnCEG = Spring.SpawnCEG
local spGetGroundHeight = Spring.GetGroundHeight

local function Jitter(x, z)
	local j = conf.targetSpacing or 0
	return x + (math.random() - 0.5) * j, z + (math.random() - 0.5) * j
end

local function RandomTarget()
	-- precomputed spots on solid ground (never in the lava): island spots are sorted by distance to the
	-- crater, so random()^1.6 makes bombs denser towards the summit
	local ring, island = conf.ringTargets, conf.islandTargets
	if ring and #ring > 0 and math.random() < conf.ringShare then
		local p = ring[math.random(#ring)]
		return Jitter(p[1], p[2])
	end
	if island and #island > 0 then
		local p = island[1 + math.floor((#island - 1) * (math.random() ^ 1.6))]
		return Jitter(p[1], p[2])
	end
	local a = math.random() * 2 * pi
	local r = conf.craterRadius + (conf.islandRadius - conf.craterRadius) * (math.random() ^ 1.6)
	return CX + r * cos(a), CZ + r * sin(a)
end

local function Impact(x, z)
	local y = spGetGroundHeight(x, z)
	spSpawnCEG("lava_explo", x, y + 10, z)
	spSpawnCEG("napalm_firewalker_small", x, y + 5, z)
	local R0 = conf.bombRadius
	local n = math.floor(R0 / 60)                      -- bigger impacts: a ring of splashes
	for k = 1, n do
		local a = (k / n + math.random() * 0.1) * 2 * pi
		local rx, rz = x + 0.55 * R0 * cos(a), z + 0.55 * R0 * sin(a)
		spSpawnCEG(k % 2 == 0 and "lava_explo" or "napalm_firewalker_small", rx, spGetGroundHeight(rx, rz) + 8, rz)
	end
	Spring.PlaySoundFile("sounds/explosion/ex_large4.wav", 3, x, y, z, "sfx")
	local R = conf.bombRadius
	local units = Spring.GetUnitsInCylinder(x, z, R)
	for i = 1, #units do
		local u = units[i]
		local d = Spring.GetUnitDefID(u)
		if d and not canFly[d] then
			local ux, _, uz = Spring.GetUnitBasePosition(u)
			local dist = sqrt((ux - x) ^ 2 + (uz - z) ^ 2)
			local dmg = conf.bombDamage * (1 - 0.75 * math.min(1, dist / R))
			Spring.AddUnitDamage(u, dmg)
		end
	end
end

function gadget:Initialize()
	for id, ud in pairs(UnitDefs) do
		canFly[id] = ud.canFly
	end
	Spring.Echo("Atlas Eruption: " .. #conf.causeways .. " causeways, flood level " .. conf.floodLevel)
end

function gadget:GameFrame(f)
	TrackTide(f)
	local st = State(f)
	local cy = conf.summitHeight
	-- crater activity
	if st == "calm" and f % 45 == 0 then
		spSpawnCEG("blacksmoke", CX + math.random(-150, 150), cy, CZ + math.random(-150, 150))
	elseif st == "warn" and f % 12 == 0 then
		spSpawnCEG("lavaburst_generic", CX + math.random(-200, 200), cy - 120, CZ + math.random(-200, 200))
		if f % 36 == 0 then spSpawnCEG("blacksmoke", CX, cy, CZ) end
	elseif (st == "rise" or st == "flood") then
		if f % 6 == 0 then
			spSpawnCEG("lava_explo", CX + math.random(-250, 250), cy - 100, CZ + math.random(-250, 250))
		end
		if f % 30 == 0 then spSpawnCEG("blacksmoke", CX, cy + 50, CZ) end
		bombAcc = bombAcc + 1 / 30
		while bombAcc >= conf.bombEverySeconds do
			bombAcc = bombAcc - conf.bombEverySeconds
			local x, z = RandomTarget()
			local hit = f + conf.bombWarnFrames
			pending[#pending + 1] = { x, z, hit }
			SendToUnsynced("AtlasBomb", x, z, hit)
		end
	else
		bombAcc = 0
	end
	for i = #pending, 1, -1 do
		local b = pending[i]
		if f >= b[3] then
			Impact(b[1], b[2])
			table.remove(pending, i)
		end
	end
end

--------------------------------------------------------------------------------
else -- UNSYNCED
--------------------------------------------------------------------------------

local bombs = {}
local causewayList
local spGetGameFrame = Spring.GetGameFrame
local spGetGroundHeight = Spring.GetGroundHeight

local function AddBomb(_, x, z, hit)
	bombs[#bombs + 1] = { x = x, z = z, hit = hit }
end

local function BuildCauseways()
	return gl.CreateList(function()
		for i = 1, #conf.causeways do
			local q = conf.causeways[i]
			local N = 24
			gl.BeginEnd(GL.QUADS, function()
				for s = 0, N - 1 do
					for k = 0, 1 do
						local t0, t1 = s / N, (s + 1) / N
						local function P(t, side)
							local a = side == 0 and q[1] or q[4]
							local b = side == 0 and q[2] or q[3]
							local x = a[1] + (b[1] - a[1]) * t
							local z = a[2] + (b[2] - a[2]) * t
							return x, z
						end
						if k == 0 then
							local x1, z1 = P(t0, 0); local x2, z2 = P(t1, 0); local x3, z3 = P(t1, 1); local x4, z4 = P(t0, 1)
							gl.Vertex(x1, spGetGroundHeight(x1, z1) + 4, z1)
							gl.Vertex(x2, spGetGroundHeight(x2, z2) + 4, z2)
							gl.Vertex(x3, spGetGroundHeight(x3, z3) + 4, z3)
							gl.Vertex(x4, spGetGroundHeight(x4, z4) + 4, z4)
						end
					end
				end
			end)
		end
	end)
end

function gadget:Initialize()
	gadgetHandler:AddSyncAction("AtlasBomb", AddBomb)
end

function gadget:Shutdown()
	gadgetHandler:RemoveSyncAction("AtlasBomb")
	if causewayList then gl.DeleteList(causewayList) end
end

function gadget:GameFrame(f)
	TrackTide(f)
	for i = #bombs, 1, -1 do
		if f > bombs[i].hit + 2 then table.remove(bombs, i) end
	end
end

local function fmt(frames)
	local s = math.max(0, floor(frames / 30 + 0.5))
	return string.format("%d:%02d", floor(s / 60), s % 60)
end

function gadget:DrawScreen()
	local st, rem = State(spGetGameFrame())
	if not st then return end
	local vsx, vsy = gl.GetViewSizes()
	local blink = (floor(Spring.GetGameSeconds() * 2) % 2 == 0)
	local txt
	if st == "calm" then
		txt = "\255\255\200\120Volcano calm  \255\255\255\255Eruption in " .. fmt(rem)
	elseif st == "warn" then
		txt = (blink and "\255\255\120\0" or "\255\255\210\120") .. "ERUPTION IN " .. fmt(rem) .. "  -  leave the causeways!"
	elseif st == "rise" then
		txt = "\255\255\60\20ERUPTION!  \255\255\255\255Lava is rising, lava bombs incoming"
	elseif st == "flood" then
		txt = "\255\255\60\20ERUPTION  \255\255\255\255Causeways flooded, lava falls in " .. fmt(rem)
	elseif st == "fall" then
		txt = "\255\255\200\60Lava falling"
	end
	gl.Text(txt, vsx * 0.5, vsy - 150, 20, "co")
end

function gadget:DrawWorldPreUnit()
	local f = spGetGameFrame()
	local st = State(f)
	local t = Spring.GetGameSeconds()
	gl.DepthTest(false)
	if st then
		if not causewayList then causewayList = BuildCauseways() end
		if st == "calm" then
			gl.Color(1.0, 0.8, 0.2, 0.07)
		elseif st == "warn" then
			gl.Color(1.0, 0.45, 0.0, 0.16 + 0.14 * sin(t * 6))
		elseif st == "rise" or st == "flood" then
			gl.Color(1.0, 0.15, 0.05, 0.22)
		else
			gl.Color(1.0, 0.6, 0.1, 0.12)
		end
		gl.CallList(causewayList)
	end
	-- bomb warnings: pulsing ring that closes in until impact
	gl.LineWidth(3)
	for i = 1, #bombs do
		local b = bombs[i]
		local left = (b.hit - f) / conf.bombWarnFrames
		if left >= 0 then
			local y = spGetGroundHeight(b.x, b.z)
			gl.Color(1.0, 0.25 + 0.3 * left, 0.05, 0.55 + 0.35 * sin(t * 14))
			gl.DrawGroundCircle(b.x, y, b.z, conf.bombRadius * (0.35 + 0.65 * left), 32)
			gl.Color(1.0, 0.2, 0.05, 0.35)
			gl.DrawGroundCircle(b.x, y, b.z, conf.bombRadius, 32)
		end
	end
	gl.LineWidth(1)
	gl.Color(1, 1, 1, 1)
	gl.DepthTest(true)
end

function gadget:DrawWorld()
	local f = spGetGameFrame()
	local cy = conf.summitHeight
	for i = 1, #bombs do
		local b = bombs[i]
		local left = (b.hit - f) / conf.bombWarnFrames         -- 1 -> 0
		if left >= 0 and left <= 1 then
			local s = 1 - left
			local gy = spGetGroundHeight(b.x, b.z)
			local x = CX + (b.x - CX) * s
			local z = CZ + (b.z - CZ) * s
			local y = cy + (gy - cy) * s + 1400 * s * (1 - s) * 2.2
			gl.PushMatrix()
			gl.Translate(x, y, z)
			gl.Billboard()
			for k = 1, 2 do
				local R = ((k == 1) and 70 or 34) * math.max(1, conf.bombRadius / 170)
				if k == 1 then gl.Color(1.0, 0.35, 0.05, 0.35) else gl.Color(1.0, 0.85, 0.4, 0.95) end
				gl.BeginEnd(GL.TRIANGLE_FAN, function()
					gl.Vertex(0, 0, 0)
					for j = 0, 16 do
						local a = j / 16 * 2 * pi
						gl.Vertex(R * cos(a), R * sin(a), 0)
					end
				end)
			end
			gl.PopMatrix()
		end
	end
	gl.Color(1, 1, 1, 1)
end

end
