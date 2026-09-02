import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      className = '',
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-all duration-200 select-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-sage/20 disabled:opacity-50 disabled:cursor-not-allowed shrink-0';

    const sizeStyles = {
      sm: 'text-xs px-2.5 py-1 rounded-lg gap-1.5 h-7',
      md: 'text-xs sm:text-[13px] px-3.5 py-1.5 rounded-xl gap-1.5 h-8.5',
      lg: 'text-xs sm:text-sm px-5 py-2.5 rounded-xl gap-2 h-10',
      icon: 'w-8 h-8 rounded-lg p-0'
    };

    const variantStyles = {
      primary:
        'bg-sage hover:bg-sage-dim active:bg-sage text-white font-semibold shadow-xs border border-transparent',
      secondary:
        'bg-sage-soft hover:bg-sage-soft/80 text-sage font-semibold border border-sage/20',
      outline:
        'bg-white hover:bg-page active:bg-edge/40 text-ink border border-edge hover:border-edge-deep shadow-2xs',
      ghost:
        'bg-transparent hover:bg-page active:bg-edge/40 text-muted hover:text-ink',
      danger:
        'bg-error hover:bg-error/90 text-white font-semibold shadow-xs'
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
        ) : (
          leftIcon
        )}
        {children && <span>{children}</span>}
        {!isLoading && rightIcon}
      </button>
    );
  }
);
Button.displayName = 'Button';
