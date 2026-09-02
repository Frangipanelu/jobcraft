import React from 'react';

export type TagVariant = 'sage' | 'warning' | 'error' | 'info' | 'neutral' | 'outline' | 'terra' | 'hazard' | 'blue';

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: TagVariant;
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
}

export const Tag: React.FC<TagProps> = ({
  variant = 'sage',
  size = 'md',
  icon,
  className = '',
  children,
  ...props
}) => {
  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 rounded-md gap-1',
    md: 'text-xs px-2.5 py-1 rounded-md gap-1.5'
  };

  const variantStyles = {
    sage: 'bg-sage-soft text-sage border border-sage/20 font-medium',
    warning: 'bg-warning-bg text-warning border border-warning/20 font-medium',
    error: 'bg-error-bg text-error border border-error/20 font-medium',
    info: 'bg-info-bg text-info border border-info/20 font-medium',
    terra: 'bg-warning-bg text-warning border border-warning/20 font-medium',
    hazard: 'bg-error-bg text-error border border-error/20 font-medium',
    neutral: 'bg-page text-muted border border-edge font-medium',
    outline: 'bg-white text-ink border border-edge font-medium shadow-2xs',
    blue: 'bg-info-bg text-info border border-info/20 font-medium'
  };

  return (
    <span
      className={`inline-flex items-center tracking-normal select-none ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="truncate">{children}</span>
    </span>
  );
};
