import { createCanvas, GlobalFonts } from '@napi-rs/canvas'
import fs from 'fs'; import path from 'path'
import { fileURLToPath } from 'url'

GlobalFonts.registerFromPath('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'DVB')

const OUT = process.argv[2]
const S = 64                        // canvas size
const items = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'))

// Colours live in tools/item_palette.json so this and
// tools/gamedata/export_item_tiles.py draw the same set.
const HERE = path.dirname(fileURLToPath(import.meta.url))
const PALETTE = JSON.parse(fs.readFileSync(path.join(HERE, 'item_palette.json'), 'utf8'))
const FAM = PALETTE.family
const PAL = PALETTE.palette
const RIM = PALETTE.rim
const famOf = c => FAM[c] || 'neutral'

function roundRect (x, r, w, h, rad) {
  x.beginPath()
  x.moveTo(rad, 0); x.lineTo(w - rad, 0); x.quadraticCurveTo(w, 0, w, rad)
  x.lineTo(w, h - rad); x.quadraticCurveTo(w, h, w - rad, h)
  x.lineTo(rad, h); x.quadraticCurveTo(0, h, 0, h - rad)
  x.lineTo(0, rad); x.quadraticCurveTo(0, 0, rad, 0); x.closePath()
}

function layout (x, label, size, maxW, maxLines) {
  x.font = `${size}px DVB`
  const words = label.split(/\s+/)
  const lines = []; let cur = ''
  for (const w of words) {
    const t = cur ? cur + ' ' + w : w
    if (x.measureText(t).width <= maxW) { cur = t; continue }
    if (cur) lines.push(cur)
    if (x.measureText(w).width > maxW) return null
    cur = w
  }
  if (cur) lines.push(cur)
  return lines.length <= maxLines ? lines : null
}

fs.mkdirSync(OUT, { recursive: true })
let written = 0, shrunk = 0
for (const it of items) {
  const fam = famOf(it.cat)
  const [bg, fg] = PAL[fam]
  const c = createCanvas(S, S), x = c.getContext('2d')
  x.clearRect(0, 0, S, S)

  roundRect(x, x, S, S, 11)
  x.fillStyle = bg; x.fill()
  x.lineWidth = 2
  x.strokeStyle = RIM[it.cls] || RIM.filler
  x.stroke()

  let lines = null, size = 0
  for (size = 15; size >= 6; size--) {
    lines = layout(x, it.label, size, S - 8, Math.floor((S - 10) / (size + 2)))
    if (lines) break
  }
  if (!lines) {
    size = 7; x.font = `${size}px DVB`
    lines = it.label.match(/.{1,9}/g).slice(0, 5); shrunk++
  }

  x.fillStyle = fg
  x.textAlign = 'center'; x.textBaseline = 'middle'
  x.font = `${size}px DVB`
  const lh = size + 2
  const top = S / 2 - ((lines.length - 1) * lh) / 2
  lines.forEach((ln, i) => x.fillText(ln, S / 2, top + i * lh))

  fs.writeFileSync(path.join(OUT, it.slug + '.png'), c.toBuffer('image/png'))
  written++
}
console.log('wrote', written, 'item images;', shrunk, 'needed a hard break')
