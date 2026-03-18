"use client"

import { ReactNode } from "react";
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
      className={cn("fixed top-0 z-10 h-14 flex items-center transition-all duration-200", className)}
      style={{
        left: state === "expanded" ? "calc(var(--sidebar-width) + 4.5rem)" : "calc(var(--sidebar-width-icon) + 4.5rem)",
      }}
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