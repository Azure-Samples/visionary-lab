import { Suspense } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

function NotFoundContent() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen text-center px-4 py-32">
      <h1 className="text-[clamp(8rem,25vw,20rem)] font-black leading-none tracking-[-0.05em] uppercase">
        404
      </h1>
      <div className="mt-8 mb-16">
        <p className="text-lg font-medium tracking-[0.2em] uppercase text-muted-foreground">
          Page not found
        </p>
      </div>
      <Button asChild className="px-12 py-6 text-sm font-bold tracking-[0.15em] uppercase">
        <Link href="/">
          Return
        </Link>
      </Button>
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