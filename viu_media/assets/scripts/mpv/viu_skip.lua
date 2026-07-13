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
}
require("mp.options").read_options(options, "viu_skip")

-- ---- in-player episode navigation --------------------------------------
if options.nav_keys then
    mp.add_forced_key_binding("SHIFT+n", "viu-next", function()
        mp.commandv("quit", "100")
    end)
    mp.add_forced_key_binding("SHIFT+p", "viu-prev", function()
        mp.commandv("quit", "101")
    end)
end

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

-- ---- opening/ending skip ------------------------------------------------
local skipped = { op = false, ed = false }

local function do_skip(kind, target)
    skipped[kind] = true
    mp.commandv("seek", target, "absolute+exact")
    mp.osd_message(kind == "op" and "Skipped opening" or "Skipped ending", 1)
    print(string.format("[viu-skip] %s -> %.1f", kind, target))
end

-- AniSkip interval-based skipping: seek out of a segment on entering it.
mp.observe_property("time-pos", "number", function(_, t)
    if t == nil then
        return
    end
    if options.op_enabled and not skipped.op and options.op_end > options.op_start
        and t >= options.op_start and t < options.op_end then
        do_skip("op", options.op_end)
    end
    if options.ed_enabled and not skipped.ed and options.ed_end > options.ed_start
        and t >= options.ed_start and t < options.ed_end then
        do_skip("ed", options.ed_end)
    end
end)

-- Chapter-based skipping. Two ways to recognise an OP/ED chapter:
--   1. by title - releases that name them "Opening"/"Ending"/etc.;
--   2. by shape - a ~90s chapter near the start (opening) or the end (ending).
--      Many releases (e.g. allanime's mp4s) ship generic "Chapter NN" titles,
--      so the title tells us nothing and the tell-tale 90s span + position is
--      the only signal. Gated on the opening_skip/ending_skip toggles.
local function chapter_kind_by_title(title)
    if not title then
        return nil
    end
    title = title:lower()
    -- "intro" is the opening in the common Intro/Episode/Credits chapter scheme
    -- (allanime encodes). "episode"/"part"/"chapter" are main content and must
    -- NOT match - the shape heuristic handles generic "Chapter NN" instead.
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

-- Returns (kind, seek_target) for the chapter at index idx, or (nil, nil).
local function classify_chapter(chapters, idx, total)
    local current = chapters[idx + 1] -- Lua tables are 1-based
    if not current then
        return nil, nil
    end
    local next_chapter = chapters[idx + 2]
    local seek_target = next_chapter and next_chapter.time or total
    local by_title = chapter_kind_by_title(current.title)
    if by_title then
        return by_title, seek_target
    end
    -- Shape heuristic: a ~90s (TV OP/ED length) chapter at an OP/ED position.
    if not (total and total > 0 and seek_target) then
        return nil, nil
    end
    local span = seek_target - current.time
    if span >= 80 and span <= 105 then
        if current.time < 0.35 * total then
            return "op", seek_target
        end
        if current.time > 0.75 * total then
            return "ed", seek_target
        end
    end
    return nil, nil
end

mp.observe_property("chapter", "number", function(_, idx)
    if idx == nil or idx < 0 then
        return
    end
    local chapters = mp.get_property_native("chapter-list") or {}
    local total = mp.get_property_native("duration")
    local kind, seek_target = classify_chapter(chapters, idx, total)
    if kind == "op" and (not options.op_enabled or skipped.op) then
        return
    end
    if kind == "ed" and (not options.ed_enabled or skipped.ed) then
        return
    end
    if kind and seek_target then
        do_skip(kind, seek_target)
    end
end)
