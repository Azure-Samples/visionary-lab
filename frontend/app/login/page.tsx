import { LoginForm } from "@/components/login-form"

export default function LoginPage() {
  return (
    <div className="flex w-full max-w-md flex-col gap-16 animate-reveal-up">
      <div className="flex flex-col items-center gap-6">
        <h1 className="text-[clamp(4rem,10vw,7rem)] font-black leading-[0.8] tracking-[-0.05em] uppercase select-none">
          Visionary
        </h1>
        {/* Red thread divider */}
        <div className="w-12 h-[2px] animate-line-draw stagger-2" style={{ background: 'var(--red-thread)' }} />
        <p className="text-[11px] font-medium tracking-[0.4em] uppercase text-muted-foreground animate-fade-in stagger-3">
          Lab
        </p>
      </div>
      <div className="animate-reveal-up stagger-4">
        <LoginForm />
      </div>
    </div>
  )
}
