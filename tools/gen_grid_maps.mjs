import { createCanvas, loadImage, GlobalFonts } from '@napi-rs/canvas'
import fs from 'fs'
GlobalFonts.registerFromPath('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','DVB')
GlobalFonts.registerFromPath('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','DV')
const REPO = process.argv[4] || '/mnt/c/Users/Russell/source/repos/rune4-poptracker'
const maps = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const outdir = process.argv[3]
const TILE=46, MARK=16, BAND=MARK+3, GAP=4, RULE=34, PW=TILE+GAP, COLS=24, PAD=14
const cache = new Map()
async function img (p) {
  if (!p) return null
  if (!cache.has(p)) { try { cache.set(p, await loadImage(REPO + '/' + p)) } catch (e) { cache.set(p, null) } }
  return cache.get(p)
}
function textTile (x, ox, oy, label) {
  x.fillStyle = '#3a3327'; x.fillRect(ox, oy, TILE, TILE)
  x.strokeStyle = 'rgba(255,255,255,.18)'; x.lineWidth = 1
  x.strokeRect(ox + .5, oy + .5, TILE - 1, TILE - 1)
  x.fillStyle = '#e8dcc0'; x.textAlign = 'center'; x.textBaseline = 'middle'
  let size, lines = null
  for (size = 10; size >= 6; size--) {
    x.font = size + 'px DV'
    const w = label.split(/\s+/), out = []; let cur = '', ok = true
    for (const t of w) {
      const s = cur ? cur + ' ' + t : t
      if (x.measureText(s).width <= TILE - 6) { cur = s; continue }
      if (cur) out.push(cur)
      if (x.measureText(t).width > TILE - 6) { ok = false; break }
      cur = t
    }
    if (!ok) continue
    if (cur) out.push(cur)
    if (out.length <= Math.floor((TILE - 6) / (size + 1))) { lines = out; break }
  }
  if (!lines) { size = 6; x.font = '6px DV'; lines = label.match(/.{1,8}/g).slice(0, 5) }
  const lh = size + 1, top = oy + TILE / 2 - ((lines.length - 1) * lh) / 2
  lines.forEach((l, i) => x.fillText(l, ox + TILE / 2, top + i * lh))
}
async function build (mapName, file, items) {
  // The gutter is only as wide as this sheet's own band labels need, and the
  // canvas stops at the widest row: a sheet of ten tiles was reserving the full
  // 24 columns and a gutter sized for the longest label in the pack.
  const probe = createCanvas(10, 10).getContext('2d')
  probe.font = 'bold 12px DVB'
  const GUT = Math.max(46, ...items.map(it =>
    Math.ceil(probe.measureText(String(it.group)).width) + 24))
  // no room for a ruler on a sheet with nothing to put in it
  const rule = items.some(it => it.sub !== null && it.sub !== undefined) ? RULE : 0
  const P = TILE + BAND + rule + GAP
  const groups = new Map()
  for (const it of items) {
    const g = it.group
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g).push(it)
  }
  // Place each group into slots rather than straight down the list: a run that
  // would leave one or two of its items stranded on the far side of a row break
  // starts on the next row instead.
  function layout (v) {
    const slot = []
    let at = 0, i = 0
    while (i < v.length) {
      let j = i
      while (j + 1 < v.length && v[j + 1].sub === v[i].sub) j++
      const len = j - i + 1
      const left = COLS - (at % COLS)
      if (left !== COLS && (left < 3 || len - left < 3) && len > left) {
        at += left                                // push the run to a fresh row
      }
      for (let k = i; k <= j; k++) slot.push(at++)
      i = j + 1
    }
    return slot
  }
  const slots = new Map()
  for (const [g, v] of groups) slots.set(g, layout(v))
  let H = PAD
  for (const [g, v] of groups) {
    H += Math.ceil((slots.get(g)[v.length - 1] + 1) / COLS) * P + 10
  }
  let used = 0
  for (const [g, v] of groups) for (const sl of slots.get(g)) used = Math.max(used, sl % COLS + 1)
  const W = GUT + used * PW + PAD
  const c = createCanvas(W, H + PAD), x = c.getContext('2d')
  const g = x.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, '#f7f0d6'); g.addColorStop(1, '#eadfb4')
  x.fillStyle = g; x.fillRect(0, 0, W, H + PAD)
  const pins = []; let y = PAD
  for (const [region, v] of groups) {
    const slot = slots.get(region)
    const rows = Math.ceil((slot[v.length - 1] + 1) / COLS)
    x.fillStyle = 'rgba(60,48,20,.07)'; x.fillRect(0, y - 5, W, rows * P + 6)
    x.strokeStyle = 'rgba(90,70,30,.28)'; x.lineWidth = 1
    x.beginPath(); x.moveTo(0, y - 5.5); x.lineTo(W, y - 5.5); x.stroke()
    x.fillStyle = '#4a3a12'; x.font = 'bold 12px DVB'
    x.textAlign = 'right'; x.textBaseline = 'middle'
    x.fillText(region, GUT - 12, y + rows * P / 2 - GAP)
    for (let i = 0; i < v.length; i++) {
      const ox = GUT + (slot[i] % COLS) * PW, oy = y + Math.floor(slot[i] / COLS) * P, ay = oy + BAND
      const im = await img(v[i].img)
      if (im) x.drawImage(im, ox, ay, TILE, TILE); else textTile(x, ox, ay, v[i].name)
      x.fillStyle = 'rgba(70,55,20,.13)'; x.fillRect(ox, oy, TILE, BAND - 2)
      pins.push({ path: v[i].path, x: Math.round(ox + TILE / 2), y: Math.round(oy + MARK / 2 + 1) })
    }
    // the sub-label ruler: one bracket per run of equal `sub` within a row.
    // The bracket is what says where a group starts and ends, so it is drawn
    // whole and its end ticks go on last; the label gets out of its way.
    for (let r = 0; r < rows; r++) {
      const idx = []
      for (let k = 0; k < v.length; k++) if (Math.floor(slot[k] / COLS) === r) idx.push(k)
      let n = 0, lastRight = [-1e9, -1e9]
      while (n < idx.length) {
        const s = v[idx[n]].sub
        let m = n
        while (m + 1 < idx.length && v[idx[m + 1]].sub === s) m++
        if (s !== null && s !== undefined) {
          const c0 = slot[idx[n]] % COLS, c1 = slot[idx[m]] % COLS
          const x0 = GUT + c0 * PW, x1 = GUT + c1 * PW + TILE
          const ry = y + r * P + BAND + TILE + 8
          x.font = 'bold 9px DVB'
          const w = Math.min(x.measureText(String(s)).width + 8, W - 4)
          // a label that would swamp its own bracket sits under it instead
          let line = w <= x1 - x0 - 8 ? 0 : 1
          let cx = Math.min(Math.max((x0 + x1) / 2, w / 2 + 2), W - w / 2 - 2)
          if (cx - w / 2 < lastRight[line]) line = line ? 0 : 1
          if (cx - w / 2 < lastRight[line]) line = 2
          const ly = ry + [0, 11, 22][line]
          lastRight[line] = Math.max(lastRight[line] || -1e9, cx + w / 2)

          x.strokeStyle = 'rgba(74,58,18,.55)'; x.lineWidth = 1
          x.beginPath()
          if (line === 0) {                       // punch the label into the line
            x.moveTo(x0 + .5, ry + .5); x.lineTo(cx - w / 2, ry + .5)
            x.moveTo(cx + w / 2, ry + .5); x.lineTo(x1 - .5, ry + .5)
          } else {
            x.moveTo(x0 + .5, ry + .5); x.lineTo(x1 - .5, ry + .5)
          }
          x.stroke()
          x.fillStyle = '#f0e8cc'; x.fillRect(cx - w / 2, ly - 5, w, 11)
          x.fillStyle = '#5b4718'
          x.textAlign = 'center'; x.textBaseline = 'middle'
          x.fillText(String(s), cx, ly + .5)
          x.strokeStyle = 'rgba(74,58,18,.8)'; x.lineWidth = 1.4
          x.beginPath()                            // end ticks last: never hidden
          x.moveTo(x0 + .7, ry - 4); x.lineTo(x0 + .7, ry + 1)
          x.moveTo(x1 - .7, ry - 4); x.lineTo(x1 - .7, ry + 1)
          x.stroke()
        }
        n = m + 1
      }
    }
    y += rows * P + 10
  }
  fs.writeFileSync(outdir + '/' + file, c.toBuffer('image/png'))
  return { mapName, file, W, H: H + PAD, pins }
}
const out = []
for (const m of maps) out.push(await build(m.mapName, m.file, m.items))
fs.writeFileSync(outdir + '/grid_split.json', JSON.stringify(out))
for (const o of out) console.log(`${o.mapName.padEnd(26)} ${o.W}x${o.H}  ${o.pins.length} tiles`)
