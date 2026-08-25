"use client"

import { type CSSProperties, type ReactNode } from "react";
import { cn } from "@/utils/cn";
import { useSidebar } from "@/components/ui/sidebar";

interface PageHeaderProps {
  title: string;
  description?: string;
  className?: string;
  children?: ReactNode;
}

export function PageHeader({
  title,
  description,
  className,
  children,
}: PageHeaderProps) {
  const { state } = useSidebar();
  
  return (
    <div 
      className={cn(
        "fixed left-16 top-0 z-10 flex h-14 items-center transition-all duration-200 sm:left-[var(--page-header-left)]",
        className,
      )}
      style={{
        "--page-header-left":
          state === "expanded"
            ? "calc(var(--sidebar-width) + 4.5rem)"
            : "calc(var(--sidebar-width-icon) + 4.5rem)",
      } as CSSProperties}
    >
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
}
