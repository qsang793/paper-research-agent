import { cn } from "@/lib/utils";
import { type HTMLMotionProps, motion } from "framer-motion";
import React from "react";

interface GlassCardProps extends HTMLMotionProps<"div"> {
    children: React.ReactNode;
    className?: string;
    gradient?: boolean;
    /** Use the solid elevated tier (--bg-1 + shadow) instead of translucent glass. */
    elevated?: boolean;
}

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
    ({ children, className, gradient = false, elevated = false, ...props }, ref) => {
        return (
            <motion.div
                ref={ref}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className={cn(
                    elevated ? "glass-panel-elevated" : "glass-panel",
                    "rounded-2xl p-6",
                    gradient && "bg-gradient-to-br from-[var(--glass-highlight)] to-transparent",
                    className
                )}
                {...props}
            >
                {children}
            </motion.div>
        );
    }
);

GlassCard.displayName = "GlassCard";
