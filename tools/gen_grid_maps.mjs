import { createCanvas, loadImage, GlobalFonts } from '@napi-rs/canvas'
import fs from 'fs'
GlobalFonts.registerFromPath('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','DVB')
GlobalFonts.registerFromPath('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','DV')
const REPO = process.argv[4] || '/mnt/c/Users/Russell/source/repos/rune4-poptracker'
const maps = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const outdir = process.argv[3]
const TILE=46, MARK=16, BAND=MARK+3, GAP=4, P=TILE+BAND+GAP, PW=TILE+GAP, COLS=24, PAD=14
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
  const groups = new Map()
  for (const it of items) {
    const g = it.group
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g).push(it)
  }
  let H = PAD
  for (const [, v] of groups) H += Math.ceil(v.length / COLS) * P + 10
  let used = 0
  for (const [, v] of groups) used = Math.max(used, Math.min(v.length, COLS))
  const W = GUT + used * PW + PAD
  const c = createCanvas(W, H + PAD), x = c.getContext('2d')
  const g = x.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, '#f7f0d6'); g.addColorStop(1, '#eadfb4')
  x.fillStyle = g; x.fillRect(0, 0, W, H + PAD)
  const pins = []; let y = PAD
  for (const [region, v] of groups) {
    const rows = Math.ceil(v.length / COLS)
    x.fillStyle = 'rgba(60,48,20,.07)'; x.fillRect(0, y - 5, W, rows * P + 6)
    x.strokeStyle = 'rgba(90,70,30,.28)'; x.lineWidth = 1
    x.beginPath(); x.moveTo(0, y - 5.5); x.lineTo(W, y - 5.5); x.stroke()
    x.fillStyle = '#4a3a12'; x.font = 'bold 12px DVB'
    x.textAlign = 'right'; x.textBaseline = 'middle'
    x.fillText(region, GUT - 12, y + rows * P / 2 - GAP)
    for (let i = 0; i < v.length; i++) {
      const ox = GUT + (i % COLS) * PW, oy = y + Math.floor(i / COLS) * P, ay = oy + BAND
      const im = await img(v[i].img)
      if (im) x.drawImage(im, ox, ay, TILE, TILE); else textTile(x, ox, ay, v[i].name)
      x.fillStyle = 'rgba(70,55,20,.13)'; x.fillRect(ox, oy, TILE, BAND - 2)
      pins.push({ path: v[i].path, x: Math.round(ox + TILE / 2), y: Math.round(oy + MARK / 2 + 1) })
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
