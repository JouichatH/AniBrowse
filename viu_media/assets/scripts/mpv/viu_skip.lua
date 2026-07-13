-- viu_skip.lua - auto-skip opening/ending for ani-browse's clean playback path.
--
-- Each episode is played by a fresh mpv, so opening/ending skip can't be driven
-- over a persistent IPC connection. Instead ani-browse fetches the AniSkip
-- intervals before launch and passes them here as script options; this script
-- seeks past a segment the first time playback enters it.
--
-- Options (via --script-opts=viu_skip-op_start=80,viu_skip-op_end=110,...):
--   op_start/op_end : opening interval in seconds (-1 = disabled)
--   ed_start/ed_end : ending interval in seconds (-1 = disabled)

local options = {
    op_start = -1,
    op_end = -1,
    ed_start = -1,
    ed_end = -1,
}
require("mp.options").read_options(options, "viu_skip")

local skipped = { op = false, ed = false }

local function maybe_skip(name, start_t, end_t)
    if skipped[name] then
        return false
    end
    if end_t <= start_t then
        return false
    end
    return function(t)
        if t ~= nil and t >= start_t and t < end_t then
            skipped[name] = true
            mp.commandv("seek", end_t, "absolute+exact")
            mp.osd_message(name == "op" and "Skipped opening" or "Skipped ending", 1)
            return true
        end
        return false
    end
end

mp.observe_property("time-pos", "number", function(_, t)
    if t == nil then
        return
    end
    local op = maybe_skip("op", options.op_start, options.op_end)
    if op then
        op(t)
    end
    local ed = maybe_skip("ed", options.ed_start, options.ed_end)
    if ed then
        ed(t)
    end
end)
