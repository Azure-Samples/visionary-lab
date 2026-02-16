"use client";

import React from 'react';
import EditorContainer from './components/EditorContainer';
import { PageHeader } from '@/components/page-header';
import dynamic from "next/dynamic";
const FadeScaleTransition = dynamic(() => import('@/components/ui/page-transition').then(m => ({ default: m.FadeScaleTransition })), { ssr: false });

export default function EditImagePage() {
  return (
    <FadeScaleTransition>
      <div className="container mx-auto py-6 space-y-6">
        <PageHeader 
          title="Edit"
        />
        
        <EditorContainer />
      </div>
    </FadeScaleTransition>
  );
} 