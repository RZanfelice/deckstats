import type { ReactNode } from 'react'

interface DataTableProps {
  columns: string[]
  rows: ReactNode[][]
  caption?: string
}

/** Tabela simples usada como gêmea acessível dos gráficos. */
export function DataTable({ columns, rows, caption }: DataTableProps) {
  return (
    <table className="w-full text-sm">
      {caption && <caption className="sr-only">{caption}</caption>}
      <thead>
        <tr className="border-b border-grid text-left text-xs text-ink-2">
          {columns.map((column, index) => (
            <th key={column} scope="col" className={`py-1 font-medium ${index > 0 ? 'text-right' : ''}`}>
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex} className="border-b border-grid last:border-0">
            {row.map((cell, index) => (
              <td key={index} className={`py-1 tabular-nums ${index > 0 ? 'text-right' : ''}`}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
