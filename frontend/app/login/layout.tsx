import React from "react";

// This is the layout for the auth pages.
// It does not include the main app sidebar or other common layout elements.
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted p-6 md:p-10">
      {children}
    </div>
  );
} 