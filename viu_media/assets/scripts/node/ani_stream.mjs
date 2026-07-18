// Persistent webtorrent stream server for ani-browse.
//
// Usage: node ani_stream.mjs <webtorrent-index-file-url> <out-dir> <port>
//
// Long-lived: one process serves a whole app session, so consecutive
// episodes reuse the node runtime, the webtorrent client, its DHT/tracker
// state and - for a season batch - the SAME connected swarm, which is where
// most of the per-episode startup used to go.
//
// Commands, one per line on stdin (magnets contain no spaces):
//   PLAY <index|-> <magnet>   select ONLY file <index> ("-" = single/largest
//                             file) and evict other torrents (bounds disk);
//                             ani-browse then plays the stream URL with mpv.
//   WARM <index|-> <magnet>   pre-add the NEXT episode's torrent: metadata +
//                             swarm connect + background-download of the file
//                             the magnet's `so=` names. The magnet's own so=
//                             selection is left as-is - a torrent that sits
//                             with EVERYTHING deselected ends up unable to
//                             serve streams later (verified live), and
//                             pre-downloading the next episode is the point.
//
// Why not `webtorrent-cli`: it drops the magnet's `so=` (select-only) param,
// so a season batch downloads EVERY episode while one is watched (verified
// live: 5.4GB in a 20s probe). This driver uses the webtorrent library
// directly and selects files explicitly. Routes are the same
// `/webtorrent/<infoHash>/<file.path>` the CLI serves.

import readline from 'node:readline'

const [, , wtIndexUrl, outDir, port] = process.argv

if (!wtIndexUrl || !outDir || !port) {
  console.error('usage: node ani_stream.mjs <webtorrent-index-file-url> <out-dir> <port>')
  process.exit(2)
}

const { default: WebTorrent } = await import(wtIndexUrl)

const client = new WebTorrent()
client.on('error', err => {
  console.error('[ani-stream] client error:', String(err && err.message ? err.message : err))
  process.exit(1)
})

const instance = client.createServer({}, 'node')
const server = instance.server
server.listen(Number(port), '127.0.0.1', () => {
  console.log('[ani-stream] listening on', port)
})

// Desired state, set synchronously from commands (the infohash is parsed out
// of the magnet, never awaited from webtorrent - add-callbacks proved
// unreliable, so all effects flow through reconcile()).
let currentHash = null // infoHash the user is watching
let currentIdxRaw = null // requested file index ("-" = single/largest)
const warmHashes = new Set() // pre-added next-episode torrents to keep

function hashOf (torrentId) {
  const m = /btih:([a-fA-F0-9]{40})/.exec(torrentId)
  return m ? m[1].toLowerCase() : null
}

// Each torrent gets its own subdirectory so cleanup of one can never touch a
// directory another torrent is being served from.
function torrentPath (torrentId) {
  const h = hashOf(torrentId)
  return h ? `${outDir}/${h}` : outDir
}

function selectOnly (torrent, idx) {
  torrent.deselect(0, torrent.pieces.length - 1)
  torrent.files.forEach((f, i) => { if (i !== idx) f.deselect() })
  if (torrent.files[idx]) torrent.files[idx].select()
}

function resolveIndex (torrent, idxRaw) {
  if (idxRaw !== '-') return Number(idxRaw)
  if (torrent.files.length === 1) return 0
  // match webtorrent's own default: the largest file
  return torrent.files.indexOf(
    torrent.files.reduce((a, b) => (a.length > b.length ? a : b))
  )
}

// Converge the client on the desired state: the current torrent plays its
// selected file, warmed torrents stay (their magnet's so= keeps them focused
// on the next episode's file), everything else is dropped. Runs after every
// command and again whenever a torrent becomes ready, so it does not matter
// which callbacks webtorrent actually delivers.
function reconcile () {
  for (const t of [...client.torrents]) {
    // A freshly added torrent has no infoHash until its magnet is parsed
    // (async); it gets reconciled by the 'torrent' event once known.
    if (!t.infoHash) continue
    if (t.infoHash === currentHash) {
      if (!t.ready) continue
      const key = `${t.infoHash}:${currentIdxRaw}`
      if (t._aniApplied === key) continue
      t._aniApplied = key
      const idx = resolveIndex(t, currentIdxRaw)
      selectOnly(t, idx)
      console.log('[ani-stream] playing', t.infoHash, 'file', idx)
    } else if (!warmHashes.has(t.infoHash)) {
      console.log('[ani-stream] evicting', t.infoHash)
      try {
        client.remove(t.infoHash, {}, () => {})
      } catch (err) {
        console.error('[ani-stream] evict failed:', String(err))
      }
    }
  }
}
client.on('torrent', reconcile)

function handle (mode, idxRaw, torrentId) {
  const hash = hashOf(torrentId)
  if (!hash) {
    console.error('[ani-stream] no infohash in torrent id')
    return
  }
  const existing = client.torrents.find(t => t.infoHash === hash)
  if (mode === 'WARM') {
    // Playing or already warmed: leave it alone.
    if (hash === currentHash || existing) return
    warmHashes.add(hash)
    client.add(torrentId, { path: torrentPath(torrentId) })
    console.log('[ani-stream] warming', hash)
    return
  }
  currentHash = hash
  currentIdxRaw = idxRaw
  warmHashes.clear() // stale warms fall to reconcile; fresh ones re-arrive
  if (!existing) client.add(torrentId, { path: torrentPath(torrentId) })
  reconcile()
}

const rl = readline.createInterface({ input: process.stdin })
rl.on('line', line => {
  const parts = line.trim().split(' ')
  if (parts.length === 3 && (parts[0] === 'PLAY' || parts[0] === 'WARM')) {
    try {
      handle(parts[0], parts[1], parts[2])
    } catch (err) {
      console.error('[ani-stream] command failed:', String(err))
    }
  } else if (line.trim()) {
    console.error('[ani-stream] bad command:', line.trim())
  }
})
// Parent (ani-browse) exited or closed stdin: shut down.
rl.on('close', () => process.exit(0))
