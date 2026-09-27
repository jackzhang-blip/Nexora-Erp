import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

function readAsset(name) {
  return readFileSync(new URL(`../resources/${name}`, import.meta.url))
}

test('桌面与安装包使用可读取的同一组品牌图标', () => {
  const png = readAsset('icon.png')
  const tray = readAsset('tray.png')
  const ico = readAsset('icon.ico')
  const icns = readAsset('icon.icns')
  const builder = readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8')
  const app = readFileSync(new URL('../src/renderer/src/App.vue', import.meta.url), 'utf8')

  // 检查真实文件头和尺寸，避免安装包配置指向损坏或过小的占位图片。
  for (const [image, width, height] of [[png, 1024, 1024], [tray, 64, 64]]) {
    assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
    assert.equal(image.readUInt32BE(16), width)
    assert.equal(image.readUInt32BE(20), height)
  }
  assert.equal(ico.subarray(0, 4).toString('hex'), '00000100')
  assert.equal(icns.subarray(0, 4).toString(), 'icns')
  assert.match(builder, /icon: resources\/icon\.icns/)
  assert.match(builder, /icon: resources\/icon\.ico/)
  assert.match(builder, /resources\/tray\.png/)
  assert.match(app, /resources\/icon\.png/)
})
