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
      <Card className="border-border">
        <CardHeader className="text-center pb-2">
          <CardTitle className="text-2xl font-black tracking-[-0.03em] uppercase">Sign In</CardTitle>
          <CardDescription className="text-xs tracking-[0.1em] uppercase text-muted-foreground mt-2">
            Continue with Microsoft
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            action={async () => {
              "use server"
              await signIn("microsoft-entra-id", { redirectTo: "/" })
            }}
            className="space-y-8"
          >
            <Button type="submit" className="w-full py-6 text-sm font-bold tracking-[0.15em] uppercase cursor-pointer">
              Sign In
            </Button>
          </form>
          <div className="text-muted-foreground *:[a]:hover:text-foreground mt-8 text-center text-[10px] tracking-[0.05em] uppercase text-balance *:[a]:underline *:[a]:underline-offset-4">
            By clicking continue, you agree to our <a href="#">Terms of Service</a>{" "}
            and <a href="#">Privacy Policy</a>.
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
