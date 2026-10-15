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
local inspire = MOCK.line("Inspire Unit")
check(inspire ~= nil, "Inspire Unit node present")
check(inspire and string.find(inspire.tip or "", "already in your armies", 1, true), "ability tooltip says existing units get it")
MOCK.click(inspire)
check(pool_text() == tostring(12 - 5), "Inspire Unit costs 5 (pool " .. tostring(pool_text()) .. ")")
local retrain = MOCK.find("vu_retrain")
check(not (retrain and retrain.visible), "no Retrain button in this edition")
local before = tonumber(pool_text())
local ma = MOCK.line("Melee Attack")
MOCK.click(ma) MOCK.click(ma)
local charge = MOCK.line("Charge")
check(charge ~= nil, "Charge node present (patch v4 stat)")
check(charge and string.find(charge.tip or "", "charge bonus", 1, true), "Charge tooltip names the stat")
MOCK.click(charge)
check(MOCK.line("Bonus vs Cavalry") ~= nil, "Bonus vs Cavalry line for foot units")
check(MOCK.line("Camouflage") ~= nil and MOCK.line("Guerrilla Deployment") ~= nil, "Camouflage and Guerrilla Deployment lines")
local spd = MOCK.line("Speed")
check(spd and string.find(spd.tip or "", "%", 1, true), "Speed tooltip shows a percentage")
local spent = before - tonumber(pool_text())
MOCK.click(MOCK.find("button_ok"))
check(MOCK.bundles["shimazu/vu_inf_spear_yari_ashigaru__stat_charge_bonus_1"], "Charge bundle applied")
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

-- Drop-in battles are blocked: the invitation's Yes button and the pre-battle button, when present.
local req = MOCK.node("panel_dropin_requester", MOCK.root)
local yes = MOCK.node("button_yes", req)
local not_now = MOCK.node("button_not_now", req)
F("PreBattle", {})
check(yes.visible == false and yes.disabled == true, "drop-in invitation: Yes button hidden")
check(not_now.visible ~= false, "drop-in invitation: Not now still available")
check(string.find(yes.tip or "", "account safe", 1, true), "drop-in invitation: tooltip explains why")
local popup = MOCK.node("popup_pre_battle", MOCK.root)
local dropin = MOCK.node("button_mp_dropin", popup)
F("PreBattle", {})
check(dropin.visible == false and dropin.disabled == true, "pre-battle drop-in button hidden")

-- Upgrade pages: Bow Ashigaru have more lines than one page holds; the rest are on page 2.
for i = 1, 10 do MOCK.battle({ "Inf_Missile_Bow_Ashigaru" }) end
MOCK.click(MOCK.node_labelled("Bow Ashigaru"))   -- the list is still open from the load check
local page_btn = MOCK.find("vu_page")
check(page_btn and page_btn.visible and string.find(MOCK.label_of(page_btn) or "", "Page 1 of 2", 1, true), "upgrade panel shows Page 1 of 2")
check(MOCK.node_labelled("Whistling Arrows") == nil, "page-2 line hidden on page 1")
check(MOCK.node_labelled("Reload") ~= nil, "page-1 line shown")
MOCK.click(page_btn)
local wa = MOCK.node_labelled("Whistling Arrows")
check(wa ~= nil and string.find(MOCK.label_of(page_btn) or "", "Page 2 of 2", 1, true), "page 2 shows its line")
check(MOCK.node_labelled("Reload") == nil, "page-1 line hidden on page 2")
MOCK.click(wa)
MOCK.click(page_btn)
check(MOCK.node_labelled("Reload") ~= nil, "page button cycles back to page 1")
MOCK.click(MOCK.find("button_ok"))
check(MOCK.bundles["shimazu/vu_inf_missile_bow_ashigaru__ab_whistling_arrows_ability_1"], "line bought on page 2 applied on OK")

RESULT = { passed = passed, failures = failures }
