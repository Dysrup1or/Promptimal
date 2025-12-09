import React from 'react';
import { cn } from '@/lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'reactor' | 'outline' | 'ghost';
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center transition-all duration-300 font-mono",
          variant === 'primary' && [
            "h-[60px] px-8",
            "bg-electric-cyan text-black font-bold tracking-wide text-[16px]",
            "hover:bg-white hover:shadow-[0_0_20px_rgba(0,240,255,0.5)]",
            "rounded-sm"
          ],
          variant === 'outline' && [
            "h-[60px] px-8",
            "border border-white/20 text-white font-medium tracking-wide text-[16px]",
            "hover:border-electric-cyan hover:text-electric-cyan hover:bg-electric-cyan/5",
            "rounded-sm"
          ],
          variant === 'reactor' && [
            "h-[56px] px-8",
            "bg-gradient-to-br from-[#8B5CF6] to-electric-cyan",
            "text-white font-bold uppercase text-[18px] tracking-wider",
            "rounded-lg",
            "hover:scale-105 hover:shadow-dual-glow"
          ],
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
