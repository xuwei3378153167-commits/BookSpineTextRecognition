// Run with Node.js + sharp (set NODE_PATH to the bundled node_modules if needed).
// SVG is the only design source; every bitmap and ICO frame is rendered from it.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const assets = path.resolve(__dirname, '../BookSpineTextRecognition/Assets');
const source = fs.readFileSync(path.join(assets, 'BookSpine.svg'));
(async () => {
  const png = await sharp(source, { density: 384 }).resize(1024, 1024).png().toBuffer();
  fs.writeFileSync(path.join(assets, 'BookSpine.png'), png);
  const sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256];
  const frames = await Promise.all(sizes.map(size => sharp(png).resize(size, size).png().toBuffer()));
  const header = Buffer.alloc(6 + sizes.length * 16);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(sizes.length, 4);
  let offset = header.length;
  frames.forEach((frame, i) => {
    const entry = 6 + i * 16;
    header[entry] = header[entry + 1] = sizes[i] === 256 ? 0 : sizes[i];
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(frame.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += frame.length;
  });
  fs.writeFileSync(path.join(assets, 'BookSpine.ico'), Buffer.concat([header, ...frames]));
  console.log(`Rendered transparent 1024px PNG and ICO frames: ${sizes.join(', ')}`);
})();
