import type { ReactNode } from "react";

export interface DataColumn {
  readonly id: string;
  readonly header: string;
  /** Right-align and use tabular figures. For counts and durations. */
  readonly numeric?: boolean;
  /** Hidden below the 'md` breakpoint. For detail that would force a sideways
   * scroll on a phone. */
  readonly secondary?: boolean;
}

export interface DataTableProps {
  /** Names the table for assistive technology. Required — an unlabelled table is
   * announced as "table" with no idea what it contains. */
  readonly caption: string;
  readonly columns: readonly DataColumn[];
  readonly children: ReactNode;
}

export function DataTable({ caption, columns, children }: DataTableProps) {
  return (
    <div className="table-scroll" tabIndex={0} role="group" aria-label={`${caption} — scrollable`}>
      <table className="data-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                scope="col"
                {...(column.numeric ? { className: "data-table-numeric" } : {})}
                {...(column.secondary ? { "data-secondary": "true" } : {})}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export interface DataRowProps {
  readonly children: ReactNode;
}

export function DataRow({ children }: DataRowProps) {
  return <tr>{children}</tr>;
}

export interface DataCellProps {
  readonly children: ReactNode;
  readonly numeric?: boolean;
  readonly secondary?: boolean;
  /** Marks the cell that contains the row`s link, so it carries the row heading
   * semantics and reads as the row's subject. */
  readonly primary?: boolean;
}

export function DataCell({ children, numeric, secondary, primary }: DataCellProps) {
  return (
    <td
      {...(numeric ? { className: "data-table-numeric" } : {})}
      {...(primary ? { className: "data-table-primary" } : {})}
      {...(secondary ? { "data-secondary": "true" } : {})}
    >
      {children}
    </td>
  );
}
