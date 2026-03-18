"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const variants = {
  fade: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
    duration: 0.3,
  },
  slide: {
    initial: { opacity: 0, x: 50 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -50 },
    duration: 0.4,
  },
  scale: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 1.05 },
    duration: 0.4,
  },
} as const;

type TransitionVariant = keyof typeof variants;

function Transition({ children, variant = "fade" }: { children: ReactNode; variant?: TransitionVariant }) {
  const pathname = usePathname();
  const v = variants[variant];

  return (
    <motion.div
      key={pathname}
      initial={v.initial}
      animate={v.animate}
      exit={v.exit}
      transition={{ duration: v.duration, ease: "easeInOut" }}
      className="w-full h-full"
    >
      {children}
    </motion.div>
  );
}

// Named exports for backward compatibility
export const PageTransition = ({ children }: { children: ReactNode }) => <Transition variant="fade">{children}</Transition>;
export const SlideTransition = ({ children }: { children: ReactNode }) => <Transition variant="slide">{children}</Transition>;
export const FadeScaleTransition = ({ children }: { children: ReactNode }) => <Transition variant="scale">{children}</Transition>; 