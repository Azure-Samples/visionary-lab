"use client"

import React, { createContext, useContext, useState, useCallback } from 'react';

interface FolderContextType {
  refreshFolders: () => void;
  folderRefreshTrigger: number;
}

const FolderContext = createContext<FolderContextType | undefined>(undefined);

export function FolderProvider({ children }: { children: React.ReactNode }) {
  const [folderRefreshTrigger, setFolderRefreshTrigger] = useState(0);

  const refreshFolders = useCallback(() => {
    setFolderRefreshTrigger(prev => prev + 1);
  }, []);

  return (
    <FolderContext.Provider value={{ refreshFolders, folderRefreshTrigger }}>
      {children}
    </FolderContext.Provider>
  );
}

export function useFolderContext() {
  const context = useContext(FolderContext);
  if (context === undefined) {
    throw new Error('useFolderContext must be used within a FolderProvider');
  }
  return context;
} 