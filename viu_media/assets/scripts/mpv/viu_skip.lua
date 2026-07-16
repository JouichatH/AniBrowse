-- viu_skip.lua - in-player navigation + opening/ending skip for ani-browse's
-- clean (non-IPC) playback path, where each episode is a fresh mpv process.
--
-- Navigation: Shift+N / Shift+P quit mpv with a sentinel exit code that the
-- launcher (MpvPlayer) maps to next/previous, then relaunches the neighbour.
--
-- Skip: two complementary sources -
--   1. AniSkip intervals passed as options (op_start/op_end/ed_start/ed_end);
--   2. chapter titles that look like an opening/ending (covers releases that
--      ship OP/ED chapters even when AniSkip has no data for the episode).
--
-- Options (via --script-opts=viu_skip-KEY=VALUE):
--   nav_keys            : enable Shift+N/P navigation (default yes)
--   op_enabled/ed_enabled : whether opening/ending skip is on (default no)
--   op_start/op_end     : AniSkip opening interval, seconds (-1 = none)
--   ed_start/ed_end     : AniSkip ending interval, seconds (-1 = none)

local options = {
    nav_keys = true,
    op_enabled = false,
    ed_enabled = false,
    op_start = -1,
    op_end = -1,
    ed_start = -1,
    ed_end = -1,
    servers_json = "",
}
require("mp.options").read_options(options, "viu_skip")

local utils = require("mp.utils")

-- ---- in-player episode navigation --------------------------------------
if options.nav_keys then
    mp.add_forced_key_binding("SHIFT+n", "viu-next", function()
        mp.commandv("quit", "100")
    end)
    mp.add_forced_key_binding("SHIFT+p", "viu-prev", function()
        mp.commandv("quit", "101")
    end)
end

-- ---- in-player server switch (no IPC) ----------------------------------
-- The launcher writes the resolved server list (name/url/headers/quality) to a
-- JSON file and passes its path as `servers_json`. Ctrl+S opens a numbered menu
-- of those servers; picking one reloads its URL in place, preserving the current
-- position and applying the server's HTTP headers. This is the quality/repair
-- safety-net: if a stream stalls or is low quality, switch without leaving mpv.
-- The app rewrites the file as background resolution completes, so the menu
-- reflects whatever servers are known at the moment it is opened.
-- (Ctrl+S is used rather than Shift+S so mpv's default screenshot binding is
-- left untouched.)
local switch_pending_seek = nil
local switch_pending_subs = nil
local menu = { open = false, overlay = nil, entries = {}, count = 0 }

local function load_server_entries()
    if options.servers_json == "" then
        return {}
    end
    local f = io.open(options.servers_json, "r")
    if not f then
        return {}
    end
    local raw = f:read("*a")
    f:close()
    local data = utils.parse_json(raw or "")
    if type(data) ~= "table" then
        return {}
    end
    return data
end

-- Escape text going into the ASS overlay so a server name can't inject styling.
local function ass_escape(s)
    return (tostring(s):gsub("\\", "\\\\"):gsub("{", "\\{"):gsub("}", "\\}"))
end

local function close_menu()
    if not menu.open then
        return
    end
    for i = 1, menu.count do
        mp.remove_key_binding("viu-srv-" .. i)
    end
    mp.remove_key_binding("viu-srv-esc")
    if menu.overlay then
        menu.overlay:remove()
    end
    menu.open = false
end

local function switch_to(entry)
    if not entry or not entry.url then
        return
    end
    switch_pending_seek = mp.get_property_number("time-pos")
    switch_pending_subs = entry.subtitles
    if type(entry.headers) == "table" then
        local hf = {}
        for k, v in pairs(entry.headers) do
            hf[#hf + 1] = tostring(k) .. ": " .. tostring(v)
        end
        mp.set_property_native("http-header-fields", hf)
    end
    mp.commandv("loadfile", entry.url, "replace")
    mp.osd_message("Switching to " .. (entry.name or "server"), 2)
    print(string.format("[viu-skip] server-switch -> %s", entry.name or "?"))
end

local function open_menu()
    local entries = load_server_entries()
    if #entries == 0 then
        mp.osd_message("No alternate servers available yet", 2)
        return
    end
    menu.entries = entries
    menu.count = math.min(#entries, 9)
    local lines = {
        string.format("{\\b1}Select server{\\b0}  (1-%d, Esc to cancel)", menu.count),
    }
    for i = 1, menu.count do
        local e = entries[i]
        local mark = e.current and "  <- current" or ""
        lines[#lines + 1] = string.format(
            "%d. %s  (%sp)%s", i, ass_escape(e.name or "?"),
            ass_escape(e.quality or "?"), mark
        )
    end
    menu.overlay = mp.create_osd_overlay("ass-events")
    menu.overlay.data = table.concat(lines, "\\N")
    menu.overlay:update()
    for i = 1, menu.count do
        mp.add_forced_key_binding(tostring(i), "viu-srv-" .. i, function()
            local e = menu.entries[i]
            close_menu()
            switch_to(e)
        end)
    end
    mp.add_forced_key_binding("ESC", "viu-srv-esc", close_menu)
    menu.open = true
end

if options.servers_json ~= "" then
    mp.add_forced_key_binding("CTRL+s", "viu-servers", function()
        if menu.open then
            close_menu()
        else
            open_menu()
        end
    end)
end

-- After a server switch reloads the stream, restore the pre-switch position and
-- (re)attach the new server's external subtitles.
mp.register_event("file-loaded", function()
    if switch_pending_seek then
        mp.commandv("seek", switch_pending_seek, "absolute+exact")
        switch_pending_seek = nil
    end
    if switch_pending_subs then
        for _, url in ipairs(switch_pending_subs) do
            mp.commandv("sub-add", url)
        end
        switch_pending_subs = nil
    end
end)

-- ---- chapter logging ----------------------------------------------------
-- Dump the embedded chapter list once the file loads. ani-browse captures mpv's
-- output and records these lines, so real OP/ED chapter-title variations can be
-- collected and the matcher below tuned against them.
mp.register_event("file-loaded", function()
    local chapters = mp.get_property_native("chapter-list") or {}
    print(string.format("[viu-chapters] count=%d", #chapters))
    for i, ch in ipairs(chapters) do
        print(string.format(
            "[viu-chapters] #%d t=%.3f title=%s",
            i, ch.time or -1, ch.title or ""
        ))
    end
end)

-- ---- opening/ending skip: reconcile two sources in one place ------------
-- This script is the ONLY spot that sees both skip sources at once: AniSkip
-- intervals arrive as script-opts, and the embedded chapters come from mpv's
-- own chapter-list. So reconciliation happens here, with a fixed precedence:
--
--     chapter-title  >  aniskip  >  (shape = log only, never skips)
--
-- A chapter named Intro/Credits/Opening/Ending is both semantic AND taken from
-- the exact encode being watched, so it beats AniSkip's external (per-show)
-- timing. A generic "Chapter NN" recognised only by its ~90s shape is a guess
-- that could cut real content, so it is logged as low-confidence and NEVER
-- auto-skipped.

-- Semantic title -> "op"/"ed"/nil. Generic titles (episode/part/chapter) return
-- nil on purpose, so they fall through to the (non-skipping) shape check.
local function title_kind(title)
    if not title then
        return nil
    end
    title = title:lower()
    if title:find("opening") or title:find("ncop") or title:find("intro")
        or title:match("^op[%s%p]?") or title == "op" then
        return "op"
    end
    if title:find("ending") or title:find("credit") or title:find("outro")
        or title:find("nced") or title:match("^ed[%s%p]?") or title == "ed" then
        return "ed"
    end
    return nil
end

-- Shape -> "op"/"ed"/nil: a ~90s (TV OP/ED length) chapter early (opening) or
-- late (ending) in the episode. Recognition only - used for LOGGING, never skip.
local function shape_kind(start_t, stop_t, total)
    if not (total and total > 0 and stop_t) then
        return nil
    end
    local span = stop_t - start_t
    if span >= 80 and span <= 105 then
        if start_t < 0.35 * total then
            return "op"
        end
        if start_t > 0.75 * total then
            return "ed"
        end
    end
    return nil
end

-- Resolved skip intervals (filled at file-loaded): resolved[kind] = {start, stop, source}.
local resolved = { op = nil, ed = nil }
local skipped = { op = false, ed = false }

local function fmt_iv(iv)
    if not iv then
        return "none"
    end
    return string.format("%.1f..%.1f(%s)", iv.start, iv.stop, iv.source)
end

-- Merge the sources into one interval per kind and log the full decision trail.
local function resolve_skips()
    local chapters = mp.get_property_native("chapter-list") or {}
    local total = mp.get_property_native("duration") or 0

    print(string.format(
        "[viu-skip] options op_enabled=%s ed_enabled=%s aniskip_op=%.1f..%.1f aniskip_ed=%.1f..%.1f",
        tostring(options.op_enabled), tostring(options.ed_enabled),
        options.op_start, options.op_end, options.ed_start, options.ed_end
    ))
    print(string.format("[viu-skip] detect count=%d duration=%.1f", #chapters, total))

    -- Gather chapter candidates per source, logging each chapter's read.
    local title_cand, shape_cand = {}, {}
    for i = 1, #chapters do
        local ch = chapters[i]
        local nxt = chapters[i + 1]
        local start_t = ch.time or 0
        local stop_t = (nxt and nxt.time) or total
        local tk = title_kind(ch.title)
        local sk = shape_kind(start_t, stop_t, total)
        if tk and not title_cand[tk] then
            title_cand[tk] = { start = start_t, stop = stop_t, source = "chapter-title" }
        end
        if sk and not shape_cand[sk] then
            shape_cand[sk] = { start = start_t, stop = stop_t, source = "chapter-shape" }
        end
        print(string.format(
            "[viu-skip] detect #%d t=%.1f span=%.1f title=%q title_kind=%s shape_kind=%s",
            i - 1, start_t, stop_t - start_t, ch.title or "",
            tk or "none", sk or "none"
        ))
    end

    -- AniSkip candidates come straight from the passed-in options.
    local aniskip = {}
    if options.op_end > options.op_start then
        aniskip.op = { start = options.op_start, stop = options.op_end, source = "aniskip" }
    end
    if options.ed_end > options.ed_start then
        aniskip.ed = { start = options.ed_start, stop = options.ed_end, source = "aniskip" }
    end

    for _, kind in ipairs({ "op", "ed" }) do
        -- Precedence: chapter-title first, then aniskip. Shape never wins.
        local chosen = title_cand[kind] or aniskip[kind]
        resolved[kind] = chosen

        -- Cross-validate when title and aniskip both exist (title still wins).
        if title_cand[kind] and aniskip[kind] then
            local dt = math.abs(title_cand[kind].start - aniskip[kind].start)
            print(string.format(
                "[viu-skip] resolve %s: chapter-title %s vs aniskip %s -> %s (chapter-title wins, dstart=%.1fs)",
                kind, fmt_iv(title_cand[kind]), fmt_iv(aniskip[kind]),
                dt <= 10 and "AGREE" or "CONFLICT", dt
            ))
        end

        -- Shape-only (no trustworthy source): recognised but deliberately not skipped.
        if not chosen and shape_cand[kind] then
            print(string.format(
                "[viu-skip] resolve %s: shape-only candidate %s -> NOT skipping (low confidence)",
                kind, fmt_iv(shape_cand[kind])
            ))
        end

        print(string.format("[viu-skip] resolved %s = %s", kind, fmt_iv(chosen)))
    end
end

mp.register_event("file-loaded", function()
    skipped.op, skipped.ed = false, false
    resolved.op, resolved.ed = nil, nil
    resolve_skips()
end)

-- Single skip path: when playback enters a resolved interval (and the matching
-- toggle is on), seek to its end. Identical handling for chapter-title and
-- aniskip since both are normalised to {start, stop}. Seeking an ending whose
-- stop is the file end lands at eof, which is what drives auto-next; a stop that
-- is a later chapter's start preserves any post-ending scene.
mp.observe_property("time-pos", "number", function(_, t)
    if t == nil then
        return
    end
    for _, kind in ipairs({ "op", "ed" }) do
        local iv = resolved[kind]
        local enabled = (kind == "op" and options.op_enabled)
            or (kind == "ed" and options.ed_enabled)
        if iv and enabled and not skipped[kind]
            and t >= iv.start and t < iv.stop then
            skipped[kind] = true
            mp.commandv("seek", iv.stop, "absolute+exact")
            mp.osd_message(kind == "op" and "Skipped opening" or "Skipped ending", 1)
            print(string.format(
                "[viu-skip] skipped %s -> %.1f via %s", kind, iv.stop, iv.source
            ))
        end
    end
end)
