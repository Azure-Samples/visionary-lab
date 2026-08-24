import React, { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { AnimatedLayout } from "@/components/animated-layout";
import { AppSidebar } from "@/components/app-sidebar";
import { ImageJobsButton } from "@/components/image-jobs-activity";
import { ThemeProvider } from "@/components/theme-provider";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { FolderProvider } from "@/context/folder-context";
import { ImageJobsProvider } from "@/context/image-jobs-context";
import { ImageSettingsProvider } from "@/context/image-settings-context";

type RootLayoutProps = {
  children: React.ReactNode;
};

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Visionary Lab",
  description: "AI-powered Content Generation",
  manifest: "/manifest.json",
  icons: {
    apple: "/logo/icon-192.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Visionary Lab",
  },
  other: {
    "mobile-web-app-capable": "yes",
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "default",
    "msapplication-TileColor": "#000000",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#000000",
};

export default async function RootLayout({ children }: RootLayoutProps) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
    >
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <meta name="format-detection" content="telephone=no" />
      </head>
      <body className="overflow-hidden">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <ImageJobsProvider>
            <ImageSettingsProvider>
              <FolderProvider>
                <div className="relative flex h-screen min-h-screen">
                  <SidebarProvider
                    style={
                      {
                        "--sidebar-width": "12rem",
                      } as React.CSSProperties
                    }
                    className="flex h-full w-full"
                  >
                    <Suspense
                      fallback={
                        <div className="h-full w-[var(--sidebar-width)] shrink-0 border-r" />
                      }
                    >
                      <AppSidebar />
                    </Suspense>
                    <SidebarInset className="flex h-full w-full flex-1 flex-col">
                      <div className="flex h-14 shrink-0 items-center gap-2 border-b px-3">
                        <SidebarTrigger />
                        <Separator orientation="vertical" className="mx-2 h-4" />
                        <div className="ml-auto flex items-center">
                          <ImageJobsButton />
                        </div>
                      </div>
                      <main className="w-full flex-1 overflow-auto transition-all duration-200">
                        <AnimatedLayout>{children}</AnimatedLayout>
                      </main>
                    </SidebarInset>
                  </SidebarProvider>
                </div>
                <Toaster />
              </FolderProvider>
            </ImageSettingsProvider>
          </ImageJobsProvider>
        </ThemeProvider>

        <Script
          id="sw-register"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/sw.js')
                    .then(function(registration) {
                      console.log('SW registered: ', registration);
                    })
                    .catch(function(registrationError) {
                      console.log('SW registration failed: ', registrationError);
                    });
                });
              }
            `,
          }}
        />

        <Script
          id="resource-preload"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              if ('fetch' in window) {
                fetch('/api/environment', { method: 'HEAD' }).catch(() => {});
              }

              if ('requestIdleCallback' in window) {
                requestIdleCallback(() => {
                  const linkEl = document.createElement('link');
                  linkEl.rel = 'prefetch';
                  linkEl.href = '/new-image';
                  document.head.appendChild(linkEl);
                });
              }
            `,
          }}
        />
      </body>
    </html>
  );
}
