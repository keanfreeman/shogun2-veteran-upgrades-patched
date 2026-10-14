-- Detect the ability patch from a campaign script (Lua 5.1; the game's working directory is the
-- game root, where empire.retail.dll lives). Returns the patch version (number) or nil.
-- The offset is the signature's file offset in the patched Steam DLL (patch.py show prints it).
local AP_SIGNATURE_OFFSET = 0x15a0190
local AP_SIGNATURE = "VU_ABILITY_PATCH "

function ability_patch_version()
	local ok, version = pcall(function()
		local f = io.open("empire.retail.dll", "rb")
		if not f then return nil end
		f:seek("set", AP_SIGNATURE_OFFSET)
		local s = f:read(#AP_SIGNATURE + 4)
		f:close()
		if s and s:sub(1, #AP_SIGNATURE) == AP_SIGNATURE then
			return tonumber(s:sub(#AP_SIGNATURE + 1):match("^%d+"))
		end
		return nil
	end)
	return ok and version or nil
end
