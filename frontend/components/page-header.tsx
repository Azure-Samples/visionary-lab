"use client"

import { ReactNode } from "react";
import { cn } from "@/utils/cn";
import { useSidebar } from "@/components/ui/sidebar";

interface BreadcrumbItem {
  label: string;
  href?: string;
  current?: boolean;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
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
      <div className="flex flex-col space-y-2">
        <div className="flex flex-col space-y-1">
          <h1 className="text-3xl font-black tracking-[-0.04em] uppercase">{title}</h1>
        </div>
        {description && (
          <p className="text-xs text-muted-foreground font-medium tracking-wide uppercase mt-1">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
} 