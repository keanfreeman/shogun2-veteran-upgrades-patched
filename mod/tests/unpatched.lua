-- The ability-patch edition on an unpatched game: stats work, abilities can't be bought.
local failures, passed = {}, 0
local function check(cond, what)
	if cond then passed = passed + 1 else failures[#failures + 1] = what end
end
local function pool_text() return MOCK.find("dy_points_to_spend").text end
local F = MOCK.fire

F("LoadingGame", {})
F("NewCampaignStarted", {})
F("UICreated", { string = "Campaign UI", component = MOCK.root })
F("FactionTurnStart", { string = "shimazu" })
for i = 1, 12 do MOCK.battle({ "Inf_Spear_Yari_Ashigaru" }) end

MOCK.click(MOCK.find("vu_button"))
MOCK.click(MOCK.node_labelled("Yari Ashigaru"))
local inspire = MOCK.line("Inspire Unit")
check(inspire ~= nil, "Inspire Unit node still shown")
check(inspire and string.find(inspire.tip or "", "game patch", 1, true), "tooltip explains the patch is missing")
MOCK.click(inspire)
check(pool_text() == "12", "ability not bought without the patch (pool " .. tostring(pool_text()) .. ")")
local charge = MOCK.line("Charge")
check(charge and string.find(charge.tip or "", "game patch", 1, true), "Charge (patch v4 stat) explains the patch is missing")
MOCK.click(charge)
check(pool_text() == "12", "Charge not bought without the patch")
local camo = MOCK.line("Camouflage")
check(camo and string.find(camo.tip or "", "game patch", 1, true), "Camouflage (patch v4 attribute) explains the patch is missing")
local tired = MOCK.line("Fatigue Resistant")
check(tired and not string.find(tired.tip or "", "game patch", 1, true), "Fatigue Resistant needs no patch (vanilla bonus)")
local ma = MOCK.line("Melee Attack")
MOCK.click(ma)
check(tonumber(pool_text()) < 12, "stats can still be bought")
MOCK.click(MOCK.find("button_ok"))
check(not MOCK.bundles["shimazu/vu_inf_spear_yari_ashigaru__ab_inspire_unit_1"], "no ability bundle applied")

for i = 1, 8 do MOCK.battle({ "Inf_Spear_Yari_Ashigaru" }, "oda") end
F("FactionTurnStart", { string = "oda" })
local ai_ability = false
for k in pairs(MOCK.bundles) do
	if string.sub(k, 1, 4) == "oda/" and string.find(k, "__ab_", 1, true) then ai_ability = true end
end
check(not ai_ability, "AI buys no abilities without the patch")

RESULT = { passed = passed, failures = failures }
