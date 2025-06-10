import React from "react";
import { MasonryGrid } from "./MasonryGrid";
import { RowBasedMasonryGrid } from "./RowBasedMasonryGrid";

interface TestItem {
  id: number;
  height: number;
  color: string;
}

const testItems: TestItem[] = [
  { id: 1, height: 120, color: "bg-red-200" },
  { id: 2, height: 80, color: "bg-blue-200" },
  { id: 3, height: 100, color: "bg-green-200" },
  { id: 4, height: 140, color: "bg-yellow-200" },
  { id: 5, height: 90, color: "bg-purple-200" },
  { id: 6, height: 110, color: "bg-pink-200" },
  { id: 7, height: 130, color: "bg-indigo-200" },
  { id: 8, height: 70, color: "bg-orange-200" },
  { id: 9, height: 95, color: "bg-teal-200" },
];

/**
 * Test component to compare column-based vs row-based masonry layouts
 * This component is for development/testing purposes only
 */
export function MasonryComparison() {
  const renderTestItem = (item: TestItem) => (
    <div
      key={item.id}
      className={`${item.color} rounded-lg p-4 flex items-center justify-center font-bold text-gray-800`}
      style={{ height: `${item.height}px` }}
    >
      {item.id}
    </div>
  );

  return (
    <div className="p-8 space-y-12">
      <div>
        <h2 className="text-2xl font-bold mb-4">Column-Based Masonry (Original)</h2>
        <p className="text-sm text-gray-600 mb-4">
          Items fill vertically first: 1,4,7 | 2,5,8 | 3,6,9
        </p>
        <MasonryGrid columns={3} gap={4}>
          {testItems.map(renderTestItem)}
        </MasonryGrid>
      </div>

      <div>
        <h2 className="text-2xl font-bold mb-4">Row-Based Masonry (New)</h2>
        <p className="text-sm text-gray-600 mb-4">
          Items fill horizontally first: 1,2,3 | 4,5,6 | 7,8,9 (but in columns for proper spacing)
        </p>
        <RowBasedMasonryGrid columns={3} gap={4}>
          {testItems.map(renderTestItem)}
        </RowBasedMasonryGrid>
      </div>
    </div>
  );
} 