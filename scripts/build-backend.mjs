import { spawnSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

// 构建缓存放在仓库的忽略目录，Mac 与 Windows 都不依赖用户级缓存写权限。
const cache = join(process.cwd(), 'build', 'pyinstaller-cache')
mkdirSync(cache, { recursive: true })
const python = process.env.NEXORA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
const result = spawnSync(python, ['-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
  '--name', 'nexora-server', '--distpath', 'build', '--workpath', 'build/pyinstaller',
  '--specpath', 'build/pyinstaller', 'backend/launcher.py'], {
  stdio: 'inherit', env: { ...process.env, PYINSTALLER_CONFIG_DIR: cache }
})
if (result.error) throw result.error
process.exit(result.status ?? 1)
