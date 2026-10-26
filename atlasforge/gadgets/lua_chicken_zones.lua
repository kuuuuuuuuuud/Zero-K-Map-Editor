--------------------------------------------------------------------------------
-- Chicken Zones (map gadget, Atlas Map Forge): chicken roosts that appear inside the player area
-- are moved at once to a valid spot in chicken land.
-- Settings: mapconfig/chicken_zones.lua
--------------------------------------------------------------------------------
function gadget:GetInfo()
	return {
		name    = "Map: Chicken Zones",
		desc    = "Moves chicken roosts out of the player area into chicken land",
		author  = "Atlas Map Forge",
		license = "GNU GPL, v2 or later",
		layer   = 10,
		enabled = true,
	}
end

if not gadgetHandler:IsSyncedCode() then
	return false
end

local CFG_FILE = "mapconfig/chicken_zones.lua"
if not VFS.FileExists(CFG_FILE) then
	return false
end
local cfg = VFS.Include(CFG_FILE)
local roostDef = UnitDefNames and UnitDefNames["roost"]
if not (cfg and roostDef) then
	return false
end
local roostDefID = roostDef.id
local gaiaTeam = Spring.GetGaiaTeamID()

local function Protected(x, z)
	for i = 1, #cfg.protect do
		local p = cfg.protect[i]
		if p.r then
			local dx, dz = x - p.x, z - p.z
			if dx * dx + dz * dz < p.r * p.r then return true end
		elseif x >= p.x0 and x <= p.x1 and z >= p.z0 and z <= p.z1 then
			return true
		end
	end
	return false
end

local function EnemyNear(x, z, radius, allyTeam)
	local units = Spring.GetUnitsInCylinder(x, z, radius)
	for i = 1, #units do
		local t = Spring.GetUnitTeam(units[i])
		if t ~= gaiaTeam and Spring.GetUnitAllyTeam(units[i]) ~= allyTeam then
			return true
		end
	end
	return false
end

local pending = {}

local function Relocate(unitID)
	local allyTeam = Spring.GetUnitAllyTeam(unitID)
	local cand = cfg.candidates
	local fallback
	for try = 1, 80 do
		local c = cand[math.random(1, #cand)]
		local x, z = c[1], c[2]
		local y = Spring.GetGroundHeight(x, z)
		if not EnemyNear(x, z, 700, allyTeam) and Spring.TestBuildOrder(roostDefID, x, y, z, 1) == 2 then
			if EnemyNear(x, z, 3500, allyTeam) then
				Spring.SetUnitPosition(unitID, x, y, z)
				return true
			end
			fallback = fallback or {x, y, z}
		end
	end
	if fallback then
		Spring.SetUnitPosition(unitID, fallback[1], fallback[2], fallback[3])
		return true
	end
	return false
end

function gadget:UnitCreated(unitID, unitDefID, teamID)
	if unitDefID ~= roostDefID then return end
	local x, _, z = Spring.GetUnitPosition(unitID)
	if x and Protected(x, z) then
		pending[#pending + 1] = unitID
	end
end

function gadget:GameFrame(n)
	if #pending == 0 then return end
	for i = #pending, 1, -1 do
		local u = pending[i]
		pending[i] = nil
		if Spring.ValidUnitID(u) then
			local ok = Relocate(u)
			Spring.Echo("[Chicken Zones] roost moved out of the player area: " .. tostring(ok))
		end
	end
end
