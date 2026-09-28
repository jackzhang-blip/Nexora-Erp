import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { test } from 'node:test'
import ts from 'typescript'

const root = resolve(import.meta.dirname, '..')
const renderer = join(root, 'src/renderer/src')

function vueFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory()
      ? vueFiles(path)
      : entry.name.endsWith('.vue')
        ? [path]
        : []
  })
}

function relativeImportExists(file, specifier) {
  const target = resolve(dirname(file), specifier)
  return [
    target,
    `${target}.ts`,
    `${target}.vue`,
    join(target, 'index.ts')
  ].some(existsSync)
}

test('根配置把 Vue 与 Electron 类型项目交给编辑器识别', () => {
  const config = ts.readConfigFile(join(root, 'tsconfig.json'), ts.sys.readFile)
  assert.equal(config.error, undefined)
  assert.deepEqual(config.config.files, [])
  assert.deepEqual(
    config.config.references.map((entry) => entry.path),
    ['./tsconfig.web.json', './tsconfig.node.json']
  )
})

test('Vue 页面中的相对导入均能从当前文件位置解析', () => {
  const missing = []
  for (const file of vueFiles(renderer)) {
    const source = readFileSync(file, 'utf8')
    for (const [, specifier] of source.matchAll(
      /\bfrom\s+['"](\.[^'"]+)['"]/g
    )) {
      // 页面搬进业务子目录后，少退一层会直接造成编辑器的 TS2307。
      if (!relativeImportExists(file, specifier)) {
        missing.push(`${file.slice(root.length + 1)} → ${specifier}`)
      }
    }
  }
  assert.deepEqual(missing, [])
})

test('业务子目录中少退一层的 store 路径会被判为无效', () => {
  const financePage = join(
    renderer,
    'views/workspace/finance/ReceivablesPayablesView.vue'
  )
  assert.equal(
    relativeImportExists(financePage, '../../store/app-store'),
    false
  )
  assert.equal(
    relativeImportExists(financePage, '../../../store/app-store'),
    true
  )
})
