-- End-to-end scenarios against tests/mock_engine.lua (ability-patch edition, game DLL patched).
-- Each check() failure is collected and reported.
local failures, passed = {}, 0
local function check(cond, what)
	if cond then passed = passed + 1 else failures[#failures + 1] = what end
end
local function count(t) local n = 0 for _ in pairs(t) do n = n + 1 end return n end
local function pool_text() return MOCK.find("dy_points_to_spend").text end
local F = MOCK.fire
local INSPIRE = "vu_inf_spear_yari_ashigaru__ab_inspire_unit_1"

-- Campaign start ----------------------------------------------------------------
F("LoadingGame", {})
F("NewCampaignStarted", {})
check(count(MOCK.locks) == 0, "no recruitment locks: this edition has no unit copies (" .. count(MOCK.locks) .. ")")
F("UICreated", { string = "Campaign UI", component = MOCK.root })
F("FactionTurnStart", { string = "shimazu" })
check(MOCK.find("vu_button") ~= nil, "Veterans HUD button created")

MOCK.add_card("Gen_Taisho", 0, true)
MOCK.add_card("Inf_Spear_Yari_Ashigaru", 2)
MOCK.add_card("Inf_Spear_Yari_Ashigaru", 0)

-- Points: 1 per battle the clan fights in, however many units/types --------------
MOCK.battle({ "Inf_Spear_Yari_Ashigaru", "Inf_Spear_Yari_Ashigaru", "Inf_Missile_Bow_Ashigaru" })
MOCK.click(MOCK.find("vu_button"))
check(pool_text() == "1", "one battle = 1 clan point (shows " .. tostring(pool_text()) .. ")")
MOCK.click(MOCK.find("button_cancel"))
MOCK.now = MOCK.now + 10
for i = 1, 11 do MOCK.battle({ "Inf_Spear_Yari_Ashigaru" }) end   -- 12 points total

-- List ----------------------------------------------------------------------------------
MOCK.click(MOCK.find("vu_button"))
check(pool_text() == "12", "pool after 12 battles (shows " .. tostring(pool_text()) .. ")")
check(MOCK.node_labelled("Yari Ashigaru") ~= nil, "Yari Ashigaru listed")
check(MOCK.node_labelled("Ikko Ikki") == nil, "Ikko Ikki units hidden for Shimazu")

-- Tree: buying an ability is a bundle, like a stat; no retraining --------------------------
MOCK.click(MOCK.node_labelled("Yari Ashigaru"))
local inspire = MOCK.node_labelled("Inspire Unit")
check(inspire ~= nil, "Inspire Unit node present")
check(inspire and string.find(inspire.tip or "", "already in your armies", 1, true), "ability tooltip says existing units get it")
MOCK.click(inspire)
check(pool_text() == tostring(12 - 5), "Inspire Unit costs 5 (pool " .. tostring(pool_text()) .. ")")
local retrain = MOCK.find("vu_retrain")
check(not (retrain and retrain.visible), "no Retrain button in this edition")
local before = tonumber(pool_text())
local ma = MOCK.node_labelled("Melee Attack")
MOCK.click(ma) MOCK.click(ma)
local spent = before - tonumber(pool_text())
MOCK.click(MOCK.find("button_ok"))
check(MOCK.bundles["shimazu/" .. INSPIRE], "Inspire Unit bundle applied on OK")
check(MOCK.bundles["shimazu/vu_inf_spear_yari_ashigaru__stat_melee_attack_mod_2"], "level-2 melee attack bundle applied")
check(#MOCK.created == 0 and #MOCK.disbanded == 0, "no units spawned or disbanded")
check(count(MOCK.locks) == 0, "still no recruitment locks")

-- Respec removes the ability bundle too ------------------------------------------------------
MOCK.click(MOCK.find("button_ok"))   -- close the list
MOCK.click(MOCK.find("vu_button"))
local p0 = tonumber(pool_text())
MOCK.click(MOCK.node_labelled("Yari Ashigaru"))
MOCK.click(MOCK.find("button_reset"))
check(tonumber(pool_text()) == p0 + 5 + spent - 2, "respec refunds everything minus 2")
MOCK.click(MOCK.find("button_ok"))
check(not MOCK.bundles["shimazu/" .. INSPIRE], "respec removed the ability bundle")
MOCK.click(MOCK.find("button_ok"))

-- AI: earns per battle, may buy abilities too now ---------------------------------------------
for i = 1, 8 do MOCK.battle({ "Inf_Spear_Yari_Ashigaru" }, "oda") end
F("FactionTurnStart", { string = "oda" })
local oda_bundles = 0
for k in pairs(MOCK.bundles) do if string.sub(k, 1, 4) == "oda/" then oda_bundles = oda_bundles + 1 end end
check(oda_bundles >= 1, "AI clan bought upgrades (" .. oda_bundles .. " bundles)")

-- Save / load round trip ------------------------------------------------------------------
F("SavingGame", {})
check(MOCK.saved.VU_POOL ~= nil and MOCK.saved.VU_AF_oda == 1, "pool and AI state saved")
local oda_before, n_ax = {}, 0
for k, v in pairs(MOCK.saved) do if string.find(k, "^VU_AX_oda__") then oda_before[k] = v n_ax = n_ax + 1 end end
check(n_ax >= 1, "AI levels saved per line key (" .. n_ax .. " values)")
local saved_pool = MOCK.saved.VU_POOL
F("LoadingGame", {})
F("UICreated", { string = "Campaign UI", component = MOCK.root })
MOCK.click(MOCK.find("vu_button"))
check(tonumber(pool_text()) == saved_pool, "pool restored after load")
F("SavingGame", {})
local same = true
for k, v in pairs(oda_before) do if MOCK.saved[k] ~= v then same = false end end
check(same, "AI levels survive a save/load round trip")

RESULT = { passed = passed, failures = failures }
