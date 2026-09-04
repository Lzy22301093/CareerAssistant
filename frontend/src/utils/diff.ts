import type { DiffRow } from '../types'

const MAX_LINES = 400

/**
 * 行级 LCS diff（红删/绿增对比展示用，纯算法零依赖）。
 * 超长文本按行截断，避免 O(n·m) 爆内存。
 */
export function diffLines(oldText: string, newText: string): DiffRow[] {
  const oldLines = (oldText ?? '').split('\n').slice(0, MAX_LINES)
  const newLines = (newText ?? '').split('\n').slice(0, MAX_LINES)
  const n = oldLines.length
  const m = newLines.length

  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = oldLines[i] === newLines[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (oldLines[i] === newLines[j]) {
      rows.push({ type: 'same', oldText: oldLines[i], newText: newLines[j] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ type: 'del', oldText: oldLines[i], newText: null })
      i++
    } else {
      rows.push({ type: 'ins', oldText: null, newText: newLines[j] })
      j++
    }
  }
  while (i < n) rows.push({ type: 'del', oldText: oldLines[i++], newText: null })
  while (j < m) rows.push({ type: 'ins', oldText: null, newText: newLines[j++] })
  return rows
}
