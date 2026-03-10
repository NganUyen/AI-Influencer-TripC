import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "bg-white dark:bg-gray-800 rounded-lg shadow-md",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "p-6 border-b border-gray-200 dark:border-gray-700",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardBody({ className, children, ...props }: CardProps) {
  return (
    <div className={cn("p-6", className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "p-6 border-t border-gray-200 dark:border-gray-700",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
