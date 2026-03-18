import React, { ReactNode } from "react";
import { cn } from "@/utils/utils";

interface RowBasedMasonryGridProps {
  children: ReactNode[];
  columns?: number;
  gap?: number;
  className?: string;
}

/**
 * Row-based masonry grid — distributes children left-to-right across columns.
 * Uses CSS-only responsive breakpoints (no JS resize listener).
 */
export function RowBasedMasonryGrid({
  children,
  columns = 3,
  gap = 4,
  className,
}: RowBasedMasonryGridProps) {
  if (!children.length) return null;

  const gapRem = `${gap * 0.25}rem`;

  function distributeIntoColumns(numCols: number): ReactNode[][] {
    const cols: ReactNode[][] = Array.from({ length: numCols }, () => []);
    React.Children.toArray(children).forEach((child, i) => {
      cols[i % numCols].push(child);
    });
    return cols;
  }

  function renderGrid(numCols: number, visibility: string) {
    return (
      <div
        className={cn("w-full", visibility, className)}
        style={{ gridTemplateColumns: `repeat(${numCols}, 1fr)`, gap: gapRem, alignItems: 'start' }}
      >
        {distributeIntoColumns(numCols).map((column, ci) => (
          <div key={ci} className="flex flex-col w-full" style={{ gap: gapRem }}>
            {column.map((child, ii) => <div key={ii} className="w-full">{child}</div>)}
          </div>
        ))}
      </div>
    );
  }

  return (
    <>
      {renderGrid(1, "grid sm:hidden")}
      {renderGrid(2, "hidden sm:grid lg:hidden")}
      {renderGrid(columns, "hidden lg:grid")}
    </>
  );
} 