import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

// Variants follow the Cohere system (see DESIGN.md): near-black pill for the
// single primary action, underlined text link for the companion action, and a
// transparent pill-outline for lightweight controls. Token-driven so they adapt
// to light/dark (in dark, --accent flips to white → white pill). Focus rings
// come from the global *:focus-visible rule. Radius lives on each variant.
const buttonVariants = cva(
    "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
    {
        variants: {
            variant: {
                // button-primary: near-black (or white-on-dark) pill CTA
                default:
                    "rounded-full bg-[var(--accent)] text-[var(--background)] hover:bg-[var(--accent-hover)]",
                // button-secondary: underlined text-only action link
                secondary:
                    "text-[var(--text-primary)] underline underline-offset-4 hover:text-[var(--accent-hover)]",
                // button-pill-outline: transparent fill, 1px border, pill radius
                outline:
                    "rounded-full border border-[var(--border-strong)] bg-transparent text-[var(--text-primary)] hover:border-[var(--accent)]",
                // Low-emphasis utility (icons, menu items)
                ghost:
                    "rounded-md bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-2)] hover:text-[var(--text-primary)]",
                // Inline editorial link (action blue)
                link: "text-[var(--link)] underline-offset-4 hover:underline",
            },
            size: {
                default: "h-10 px-6 py-2",
                sm: "h-9 px-4",
                lg: "h-12 px-8 text-[15px]",
                icon: "h-10 w-10",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
)

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, asChild = false, ...props }, ref) => {
        const Comp = asChild ? Slot : "button"
        return (
            <Comp
                className={cn(buttonVariants({ variant, size, className }))}
                ref={ref}
                {...props}
            />
        )
    }
)
Button.displayName = "Button"

export { Button, buttonVariants }
