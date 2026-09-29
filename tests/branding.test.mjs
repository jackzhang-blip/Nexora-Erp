import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

function readAsset(name) {
  return readFileSync(new URL(`../resources/${name}`, import.meta.url))
}

test('桌面与安装包使用可读取的同一组品牌图标', () => {
  const png = readAsset('icon.png')
  const tray = readAsset('tray.png')
  const tray2x = readAsset('tray@2x.png')
  const ico = readAsset('icon.ico')
  const icns = readAsset('icon.icns')
  const builder = readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8')
  const brand = readFileSync(new URL('../src/renderer/src/assets/brand.ts', import.meta.url), 'utf8')

  // 核对菜单栏的逻辑尺寸及高清尺寸，防止重新生成时把图标放大回 64 像素。
  for (const [image, width, height] of [[png, 1024, 1024], [tray, 16, 16], [tray2x, 32, 32]]) {
    assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
    assert.equal(image.readUInt32BE(16), width)
    assert.equal(image.readUInt32BE(20), height)
  }
  assert.equal(ico.subarray(0, 4).toString('hex'), '00000100')
  assert.equal(icns.subarray(0, 4).toString(), 'icns')
  assert.match(builder, /icon: resources\/icon\.icns/)
  assert.match(builder, /icon: resources\/icon\.ico/)
  assert.match(builder, /resources\/tray\.png/)
  assert.match(builder, /resources\/tray@2x\.png/)
  assert.match(brand, /resources\/icon\.png/)
})
