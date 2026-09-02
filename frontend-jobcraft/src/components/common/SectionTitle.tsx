import React from 'react';

export interface SectionTitleProps {
  num?: string | number;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const SectionTitle: React.FC<SectionTitleProps> = ({
  num,
  title,
  subtitle,
  badge,
  action,
  className = ''
}) => {
  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-edge ${className}`}
    >
      <div className="flex items-center gap-2.5">
        {num !== undefined && (
          <span className="w-6 h-6 rounded-full bg-sage-soft text-sage inline-flex items-center justify-center text-[11px] font-bold shrink-0">
            {typeof num === 'number' ? String(num).padStart(2, '0') : num}
          </span>
        )}
        <h2 className="text-[15px] font-bold text-ink tracking-tight">{title}</h2>
        {badge}
      </div>
      {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};
