import { cn } from "@/utils/utils"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { signIn } from "@/auth"

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div className={cn("flex flex-col gap-8", className)} {...props}>
      <Card className="border-2 border-border hover:border-foreground transition-colors duration-300">
        <CardHeader className="text-center pb-2 pt-8">
          <CardTitle className="text-2xl font-black tracking-[-0.03em] uppercase">Sign In</CardTitle>
          <CardDescription className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground mt-3">
            Continue with Microsoft
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-8">
          <form
            action={async () => {
              "use server"
              await signIn("microsoft-entra-id", { redirectTo: "/" })
            }}
            className="space-y-8"
          >
            <Button type="submit" className="w-full py-7 text-[11px] font-bold tracking-[0.2em] uppercase cursor-pointer transition-all duration-300 hover:tracking-[0.3em]">
              Sign In
            </Button>
          </form>
          <div className="text-muted-foreground *:[a]:hover:text-foreground mt-8 text-center text-[9px] tracking-[0.08em] uppercase text-balance *:[a]:underline *:[a]:underline-offset-4 *:[a]:decoration-[var(--red-thread)]">
            By clicking continue, you agree to our <a href="#">Terms of Service</a>{" "}
            and <a href="#">Privacy Policy</a>.
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
