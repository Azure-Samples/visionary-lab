import { LoginForm } from "@/components/login-form"

export default function LoginPage() {
  return (
    <div className="flex w-full max-w-md flex-col gap-12">
      <div className="flex flex-col items-center gap-4">
        <h1 className="text-[clamp(3rem,8vw,6rem)] font-black leading-none tracking-[-0.05em] uppercase">
          Visionary
        </h1>
        <p className="text-xs font-medium tracking-[0.3em] uppercase text-muted-foreground">
          Lab
        </p>
      </div>
      <LoginForm />
    </div>
  )
}
