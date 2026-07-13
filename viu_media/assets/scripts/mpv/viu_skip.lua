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

-- ---- opening/ending skip ------------------------------------------------
local skipped = { op = false, ed = false }

local function do_skip(kind, target)
    skipped[kind] = true
    mp.commandv("seek", target, "absolute+exact")
    mp.osd_message(kind == "op" and "Skipped opening" or "Skipped ending", 1)
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

-- Chapter-title-based skipping: when AniSkip has no data, many releases still
-- name their OP/ED chapters. Seek to the end of such a chapter the first time
-- we enter it (to the next chapter's start, so a post-ending scene still plays).
local function chapter_kind(title)
    if not title then
        return nil
    end
    title = title:lower()
    if title:find("opening") or title:find("ncop") or title:match("^op[%s%p]?")
        or title == "op" then
        return "op"
    end
    if title:find("ending") or title:find("credit") or title:find("outro")
        or title:find("nced") or title:match("^ed[%s%p]?") or title == "ed" then
        return "ed"
    end
    return nil
end

mp.observe_property("chapter", "number", function(_, idx)
    if idx == nil or idx < 0 then
        return
    end
    local chapters = mp.get_property_native("chapter-list") or {}
    local current = chapters[idx + 1] -- Lua tables are 1-based
    if not current then
        return
    end
    local kind = chapter_kind(current.title)
    if kind == nil then
        return
    end
    if kind == "op" and (not options.op_enabled or skipped.op) then
        return
    end
    if kind == "ed" and (not options.ed_enabled or skipped.ed) then
        return
    end
    local next_chapter = chapters[idx + 2]
    if next_chapter and next_chapter.time then
        do_skip(kind, next_chapter.time)
    end
end)
