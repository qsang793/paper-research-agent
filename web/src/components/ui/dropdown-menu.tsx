"use client"

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cn } from "@/lib/utils"

const DropdownMenu = ({ children }: { children: React.ReactNode }) => {
    const [isOpen, setIsOpen] = React.useState(false)
    const containerRef = React.useRef<HTMLDivElement>(null)

    React.useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside)
        return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [])

    return (
        <div ref={containerRef} className="relative inline-block text-left">
            {React.Children.map(children, (child) => {
                if (React.isValidElement<{
                    isOpen?: boolean
                    setIsOpen?: (v: boolean) => void
                }>(child)) {
                    return React.cloneElement(child, { isOpen, setIsOpen })
                }
                return child
            })}
        </div>
    )
}

const DropdownMenuTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean; isOpen?: boolean; setIsOpen?: (v: boolean) => void }
>(({ className, children, asChild, isOpen, setIsOpen, onClick, ...props }, ref) => {
    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
        setIsOpen?.(!isOpen)
        onClick?.(event)
    }

    if (asChild && React.isValidElement(children)) {
        return (
            <Slot
                ref={ref}
                onClick={handleClick}
                {...props}
            >
                {children}
            </Slot>
        )
    }

    return (
        <button
            ref={ref}
            onClick={handleClick}
            className={cn("inline-flex items-center justify-center", className)}
            {...props}
        >
            {children}
        </button>
    )
})
DropdownMenuTrigger.displayName = "DropdownMenuTrigger"

const DropdownMenuContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & { align?: "start" | "end" | "center"; side?: "top" | "bottom" | "left" | "right"; isOpen?: boolean; setIsOpen?: (v: boolean) => void }
>(({ className, align = "center", side = "bottom", isOpen, setIsOpen, ...props }, ref) => {
    if (!isOpen) return null

    return (
        <div
            ref={ref}
            data-side={side}
            data-state={isOpen ? "open" : "closed"}
            className={cn(
                "absolute z-50 min-w-[8rem] overflow-visible rounded-md border border-[var(--border-strong)] bg-[var(--bg-2)] p-1 text-[var(--text-primary)] shadow-[var(--shadow-lg)] transition-all",
                "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
                "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
                "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",

                // Align logic
                align === "start" && "left-0",
                align === "end" && "right-0",
                align === "center" && "left-1/2 -translate-x-1/2",

                // Side logic
                side === "bottom" && "top-full mt-2",
                side === "top" && "bottom-full mb-2",

                className
            )}
            onClick={(e) => {
                // Don't close if clicking on submenu or items with submenu
                const target = e.target as HTMLElement
                if (target.closest('[data-has-submenu]') || target.closest('[data-submenu]')) {
                    e.stopPropagation()
                    return
                }
                setIsOpen?.(false)
            }}
            {...props}
        />
    )
})
DropdownMenuContent.displayName = "DropdownMenuContent"

const DropdownMenuItem = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & { inset?: boolean }
>(({ className, inset, ...props }, ref) => (
    <div
        ref={ref}
        className={cn(
            "relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-[var(--bg-3)] focus:bg-[var(--bg-3)] data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
            inset && "pl-8",
            className
        )}
        {...props}
    />
))
DropdownMenuItem.displayName = "DropdownMenuItem"

export {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
}
