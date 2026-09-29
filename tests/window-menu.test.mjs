import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { join } from 'node:path'
import { test } from 'node:test'
import ts from 'typescript'

// 执行实际窗口创建函数，验证首次启动和托盘重建窗口都应用菜单策略。
const source = readFileSync(new URL('../src/main/index.ts', import.meta.url), 'utf8')
const ast = ts.createSourceFile('index.ts', source, ts.ScriptTarget.Latest, true)
const createWindow = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'createWindow')
assert.ok(createWindow)
const script = ts.transpileModule(createWindow.getText(ast), {
  compilerOptions: { target: ts.ScriptTarget.ES2022 }
}).outputText

for (const platform of ['win32', 'darwin', 'linux']) {
  for (const development of [true, false]) {
    test(`${platform} ${development ? '开发' : '安装'}模式窗口菜单和重建行为`, () => {
      const windows = []
      class BrowserWindow {
        constructor(options) {
          this.options = options
          this.calls = []
          this.webContents = { setWindowOpenHandler() {} }
          windows.push(this)
        }
        setMenu(value) { this.calls.push(['menu', value]) }
        on() {}
        loadURL() { this.calls.push(['loadURL']) }
        loadFile() { this.calls.push(['loadFile']) }
      }
      runInNewContext(`${script}; createWindow(); createWindow();`, {
        BrowserWindow, join, __dirname: '/app/main', mainWindow: null,
        process: { platform, env: development ? { ELECTRON_RENDERER_URL: 'http://localhost:5173' } : {} }
      })
      assert.equal(windows.length, 2)
      for (const window of windows) {
        assert.deepEqual(window.calls, [
          ...(platform === 'win32' ? [['menu', null]] : []),
          [development ? 'loadURL' : 'loadFile']
        ])
        assert.equal(window.options.frame, undefined)
        assert.equal(window.options.webPreferences.contextIsolation, true)
        assert.equal(window.options.webPreferences.nodeIntegration, false)
      }
    })
  }
}
