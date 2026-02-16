import { Suspense } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

function NotFoundContent() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen text-center px-4 py-32 relative overflow-hidden">
      {/* The Red Thread — a horizontal rule */}
      <div className="absolute top-1/2 left-0 w-full h-[2px] -translate-y-1/2 opacity-20"
        style={{ background: 'var(--red-thread)' }}
      />

      <h1 className="text-[clamp(10rem,30vw,24rem)] font-black leading-[0.75] tracking-[-0.06em] uppercase animate-reveal-up select-none">
        404
      </h1>

      <div className="mt-12 mb-20 animate-reveal-up stagger-2">
        <p className="text-sm font-medium tracking-[0.35em] uppercase text-muted-foreground">
          Page not found
        </p>
      </div>

      <div className="animate-reveal-up stagger-3">
        <Button asChild className="px-16 py-7 text-[11px] font-bold tracking-[0.2em] uppercase cursor-pointer border-2 border-foreground bg-transparent text-foreground hover:bg-foreground hover:text-background transition-all duration-300" variant="outline">
          <Link href="/">
            Return
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default function NotFound() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center min-h-screen">
        <p className="text-sm tracking-[0.15em] uppercase">Loading...</p>
      </div>
    }>
      <NotFoundContent />
    </Suspense>
  );
} 