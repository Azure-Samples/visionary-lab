import React, { ReactNode, useEffect, useState } from "react";
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
 * Uses column-based layout for proper height handling but with row-first distribution
 */
export function RowBasedMasonryGrid({
  children,
  columns = 3,
  gap = 4,
  className,
}: RowBasedMasonryGridProps) {
  const [currentColumns, setCurrentColumns] = useState(columns);

  // Responsive column calculation
  useEffect(() => {
    const updateColumns = () => {
      if (window.innerWidth < 640) {
        setCurrentColumns(1);
      } else if (window.innerWidth < 1024) {
        setCurrentColumns(2);
      } else {
        setCurrentColumns(columns);
      }
    };

    // Set initial value
    updateColumns();

    // Add event listener
    window.addEventListener('resize', updateColumns);
    
    // Cleanup
    return () => window.removeEventListener('resize', updateColumns);
  }, [columns]);

  // If no children, return null
  if (!children.length) return null;

  // Distribute children into columns but with row-first ordering
  const distributeIntoColumns = () => {
    const columnArrays: ReactNode[][] = Array.from({ length: currentColumns }, () => []);
    const childrenArray = React.Children.toArray(children);
    
    // Fill row by row (horizontally first)
    childrenArray.forEach((child, index) => {
      const columnIndex = index % currentColumns;
      columnArrays[columnIndex].push(child);
    });
    
    return columnArrays;
  };

  const columnArrays = distributeIntoColumns();

  return (
    <div
      className={cn("w-full", className)}
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${currentColumns}, 1fr)`,
        gap: `${gap * 0.25}rem`,
        alignItems: 'start',
      }}
    >
      {columnArrays.map((column, columnIndex) => (
        <div
          key={`column-${columnIndex}`}
          className="flex flex-col w-full"
          style={{
            gap: `${gap * 0.25}rem`,
          }}
        >
          {column.map((child, itemIndex) => (
            <div key={`col-${columnIndex}-item-${itemIndex}`} className="w-full">
              {child}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
} 