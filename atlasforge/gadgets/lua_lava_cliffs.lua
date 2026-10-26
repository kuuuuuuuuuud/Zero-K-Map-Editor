--------------------------------------------------------------------------------
-- Atlas Lava Cliffs (map gadget, Atlas Map Forge)
-- Ground units on unreachable high ground (lava texture) take slow damage.
-- Area: mapconfig/atlas_lava_cliffs.lua
--------------------------------------------------------------------------------
function gadget:GetInfo()
	return {
		name    = "Atlas Lava Cliffs",
		desc    = "Slow damage for ground units on lava-covered cliffs (map gadget)",
		author  = "Atlas Map Forge",
		layer   = 0,
		enabled = true,
	}
end

if not gadgetHandler:IsSyncedCode() then
	return
end

local CONF_FILE = "mapconfig/atlas_lava_cliffs.lua"
local PERIOD = 15

local conf
local grid = {}
local CELL, NX, NZ = 32, 0, 0
local canFly = {}

local spGetAllUnits = Spring.GetAllUnits
local spGetUnitDefID = Spring.GetUnitDefID
local spGetUnitBasePosition = Spring.GetUnitBasePosition
local spGetGroundHeight = Spring.GetGroundHeight
local spGetUnitHealth = Spring.GetUnitHealth
local spGetUnitTransporter = Spring.GetUnitTransporter
local spAddUnitDamage = Spring.AddUnitDamage
local floor, max = math.floor, math.max

function gadget:Initialize()
	if not VFS.FileExists(CONF_FILE) then
		gadgetHandler:RemoveGadget(self)
		return
	end
	conf = VFS.Include(CONF_FILE)
	CELL, NX, NZ = conf.cell, conf.nx, conf.nz
	local count = 0
	for z = 1, #conf.rows do
		local x, on = 0, false
		for run in string.gmatch(conf.rows[z], "%d+") do
			local n = tonumber(run)
			if on then
				for i = x, x + n - 1 do
					grid[(z - 1) * NX + i] = true
					count = count + 1
				end
			end
			x = x + n
			on = not on
		end
	end
	for id, ud in pairs(UnitDefs) do
		canFly[id] = ud.canFly
	end
	Spring.Echo("Atlas Lava Cliffs: " .. count .. " cells")
end

function gadget:GameFrame(f)
	if f % PERIOD ~= 0 then
		return
	end
	local units = spGetAllUnits()
	for i = 1, #units do
		local u = units[i]
		local d = spGetUnitDefID(u)
		if d and not canFly[d] and not spGetUnitTransporter(u) then
			local x, y, z = spGetUnitBasePosition(u)
			if x then
				local cx, cz = floor(x / CELL), floor(z / CELL)
				if cx >= 0 and cz >= 0 and cx < NX and cz < NZ and grid[cz * NX + cx] then
					if y < spGetGroundHeight(x, z) + 24 then
						local _, maxHP = spGetUnitHealth(u)
						if maxHP then
							spAddUnitDamage(u, max(conf.minDps, maxHP * conf.pctDps) * PERIOD / 30)
						end
					end
				end
			end
		end
	end
end
