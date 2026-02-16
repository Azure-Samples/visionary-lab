import React, { ReactNode } from "react";
import { cn } from "@/utils/utils";

interface RowBasedMasonryGridProps {
  children: ReactNode[];
  columns?: number;
  gap?: number;
  className?: string;
}

/**
 * A row-based masonry grid layout component that maintains proper spacing
 * Distributes children into columns but fills horizontally first (row-based ordering)
 * Uses CSS-only responsive breakpoints instead of JS resize listeners
 */
export function RowBasedMasonryGrid({
  children,
  columns = 3,
  gap = 4,
  className,
}: RowBasedMasonryGridProps) {
  // If no children, return null
  if (!children.length) return null;

  // Distribute children into columns for each breakpoint
  // We render all breakpoint variants and use CSS to show the right one
  const distributeIntoColumns = (numCols: number) => {
    const columnArrays: ReactNode[][] = Array.from({ length: numCols }, () => []);
    const childrenArray = React.Children.toArray(children);
    
    // Fill row by row (horizontally first)
    childrenArray.forEach((child, index) => {
      const columnIndex = index % numCols;
      columnArrays[columnIndex].push(child);
    });
    
    return columnArrays;
  };

  const gapRem = `${gap * 0.25}rem`;

  return (
    <>
      {/* 1 column: < 640px */}
      <div
        className={cn("w-full sm:hidden", className)}
        style={{ display: 'grid', gridTemplateColumns: '1fr', gap: gapRem, alignItems: 'start' }}
      >
        {distributeIntoColumns(1).map((column, ci) => (
          <div key={ci} className="flex flex-col w-full" style={{ gap: gapRem }}>
            {column.map((child, ii) => <div key={ii} className="w-full">{child}</div>)}
          </div>
        ))}
      </div>
      {/* 2 columns: 640px–1023px */}
      <div
        className={cn("w-full hidden sm:grid lg:hidden", className)}
        style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: gapRem, alignItems: 'start' }}
      >
        {distributeIntoColumns(2).map((column, ci) => (
          <div key={ci} className="flex flex-col w-full" style={{ gap: gapRem }}>
            {column.map((child, ii) => <div key={ii} className="w-full">{child}</div>)}
          </div>
        ))}
      </div>
      {/* N columns: >= 1024px */}
      <div
        className={cn("w-full hidden lg:grid", className)}
        style={{ gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: gapRem, alignItems: 'start' }}
      >
        {distributeIntoColumns(columns).map((column, ci) => (
          <div key={ci} className="flex flex-col w-full" style={{ gap: gapRem }}>
            {column.map((child, ii) => <div key={ii} className="w-full">{child}</div>)}
          </div>
        ))}
      </div>
    </>
  );
} 