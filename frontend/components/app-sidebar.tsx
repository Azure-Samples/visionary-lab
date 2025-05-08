"use client"

import { FolderIcon, ImageIcon, ImagePlus, Settings, ChevronDown, ChevronRight, PlusCircle } from "lucide-react"
import Link from 'next/link';
import Image from 'next/image';
import { useTheme } from "next-themes";
import { ThemeToggle } from "@/components/theme-toggle";
import { useEffect, useState } from "react";
import { fetchFolders, MediaType } from "@/services/api";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

// Create section items
const createItems = [
  {
    title: "Images",
    url: "/",
    icon: ImagePlus,
  },
]

// Find section items
const findItems = [
  {
    title: "Settings",
    url: "/settings",
    icon: Settings,
  },
]

export function AppSidebar() {
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);
  const [folderHierarchy, setFolderHierarchy] = useState<any>({});
  const [isImageFoldersOpen, setIsImageFoldersOpen] = useState(true);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentFolderParam = searchParams.get('folder');
  
  // Only render logo after mounted on client to avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch folders on component mount
  useEffect(() => {
    const loadFolders = async () => {
      try {
        console.log('AppSidebar: Attempting to fetch folders');
        const response = await fetchFolders(MediaType.IMAGE);
        console.log('AppSidebar: Folders fetched successfully:', response);
        setFolders(response.folders || []);
        setFolderHierarchy(response.folder_hierarchy || {});
      } catch (error) {
        console.error("AppSidebar: Error fetching folders:", error);
        // Set empty arrays/objects to prevent UI errors
        setFolders([]);
        setFolderHierarchy({});
      }
    };

    // Add a small delay to ensure environment variables are loaded
    setTimeout(() => {
      loadFolders();
    }, 500);
  }, []);

  // Determine logo based on theme
  const logoSrc = mounted && theme === "dark" 
    ? "/logo/logo-light.png"  // Light logo for dark theme (white/bright logo)
    : "/logo/logo-dark.png";  // Dark logo for light theme (black/dark logo)
    
  // Navigate to images page with folder filter
  const handleFolderClick = (folderPath: string) => {
    router.push(`/images?folder=${encodeURIComponent(folderPath)}`);
  };

  // Check if a folder link is active
  const isFolderActive = (folderPath: string | null) => {
    if (!folderPath) {
      // "All Images" is active when no folder parameter is present
      return pathname === '/images' && !currentFolderParam;
    }
    
    // Otherwise check if the folder parameter matches the current folder
    return currentFolderParam === folderPath;
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="p-4 group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:justify-center">
        {mounted ? (
          <>
            <div className="flex items-center group-data-[collapsible=icon]:hidden">
              <Image 
                src={logoSrc} 
                alt="Visionary Lab" 
                width={30} 
                height={30} 
                className="mr-2"
                onError={(e) => {
                  // Fallback to SVG if PNG fails to load
                  const imgElement = e.currentTarget;
                  if (logoSrc.endsWith('.png')) {
                    imgElement.src = logoSrc.replace('.png', '.svg');
                  }
                }}
              />
              <h2 className="font-semibold text-lg">Visionary Lab</h2>
            </div>
            <div className="hidden group-data-[collapsible=icon]:flex items-center justify-center">
              <Image 
                src={logoSrc} 
                alt="Visionary Lab" 
                width={24} 
                height={24}
                onError={(e) => {
                  // Fallback to SVG if PNG fails to load
                  const imgElement = e.currentTarget;
                  if (logoSrc.endsWith('.png')) {
                    imgElement.src = logoSrc.replace('.png', '.svg');
                  }
                }}
              />
            </div>
          </>
        ) : (
          // Placeholder during SSR
          <div className="h-8 group-data-[collapsible=icon]:h-6"></div>
        )}
      </SidebarHeader>
      <SidebarContent>
        {/* Create Section */}
        <SidebarGroup>
          <SidebarGroupLabel className="group-data-[collapsible=icon]:hidden">Create</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {createItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <Link href={item.url} passHref legacyBehavior>
                    <SidebarMenuButton asChild className="group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-2">
                      <a>
                        <item.icon className="h-4 w-4 group-data-[collapsible=icon]:h-5 group-data-[collapsible=icon]:w-5" />
                        <span className="group-data-[collapsible=icon]:hidden">{item.title}</span>
                      </a>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Find Section */}
        <SidebarGroup>
          <SidebarGroupLabel className="group-data-[collapsible=icon]:hidden">Find</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {findItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <Link href={item.url} passHref legacyBehavior>
                    <SidebarMenuButton asChild className="group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-2">
                      <a>
                        <item.icon className="h-4 w-4 group-data-[collapsible=icon]:h-5 group-data-[collapsible=icon]:w-5" />
                        <span className="group-data-[collapsible=icon]:hidden">{item.title}</span>
                      </a>
                    </SidebarMenuButton>
                  </Link>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Image Folders Section */}
        <div className="group-data-[collapsible=icon]:hidden">
          <Collapsible
            open={isImageFoldersOpen}
            onOpenChange={setIsImageFoldersOpen}
            className="w-full"
          >
            <SidebarGroup>
              <SidebarGroupLabel asChild>
                <CollapsibleTrigger className="flex w-full items-center justify-between">
                  <span>Image Folders</span>
                  <ChevronDown className="h-4 w-4 transition-transform duration-200" 
                    style={{ 
                      transform: isImageFoldersOpen ? 'rotate(0deg)' : 'rotate(-90deg)' 
                    }}
                  />
                </CollapsibleTrigger>
              </SidebarGroupLabel>
              <CollapsibleContent>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {/* Show All Images option */}
                    <SidebarMenuItem>
                      <Link href="/images" passHref legacyBehavior>
                        <SidebarMenuButton 
                          asChild
                          data-active={isFolderActive(null)}
                          className="data-[active=true]:bg-accent"
                        >
                          <a>
                            <ImageIcon className="h-4 w-4 mr-2" />
                            <span>All Images</span>
                          </a>
                        </SidebarMenuButton>
                      </Link>
                    </SidebarMenuItem>
                    
                    {/* Folder List */}
                    {folders.map((folder) => (
                      <SidebarMenuItem key={folder}>
                        <SidebarMenuButton 
                          asChild
                          data-active={isFolderActive(folder)}
                          className="data-[active=true]:bg-accent"
                          onClick={() => handleFolderClick(folder)}
                        >
                          <a>
                            <FolderIcon className="h-4 w-4 mr-2" />
                            <span>{folder.split('/').pop() || folder}</span>
                          </a>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </CollapsibleContent>
            </SidebarGroup>
          </Collapsible>
        </div>
      </SidebarContent>
      
      {/* Add a footer with theme toggle */}
      <SidebarFooter className="p-4 group-data-[collapsible=icon]:p-2 border-t">
        <div className="flex items-center justify-between group-data-[collapsible=icon]:justify-center">
          <span className="text-sm text-muted-foreground group-data-[collapsible=icon]:hidden">Theme</span>
          <ThemeToggle />
        </div>
      </SidebarFooter>
    </Sidebar>
  )
} 