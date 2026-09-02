import React from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

export const ToastContainer: React.FC = () => {
  const { toasts, dismissToast } = useJobCraft();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-md w-full pointer-events-none">
      {toasts.map((toast) => {
        let icon = <CheckCircle2 className="w-4 h-4 text-sage shrink-0 mt-0.5" />;
        let borderColor = 'border-sage/30 bg-white text-ink';

        if (toast.type === 'error') {
          icon = <AlertCircle className="w-4 h-4 text-error shrink-0 mt-0.5" />;
          borderColor = 'border-error/30 bg-white text-ink';
        } else if (toast.type === 'warning') {
          icon = <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />;
          borderColor = 'border-warning/30 bg-white text-ink';
        } else if (toast.type === 'info') {
          icon = <Info className="w-4 h-4 text-info shrink-0 mt-0.5" />;
          borderColor = 'border-info/30 bg-white text-ink';
        }

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-lg shadow-black/5 transition-all duration-300 animate-in fade-in slide-in-from-bottom-3 ${borderColor}`}
          >
            {icon}
            <div className="flex-1 min-w-0">
              <h4 className="text-xs sm:text-[13px] font-bold leading-tight text-ink">{toast.title}</h4>
              {toast.message && (
                <p className="text-xs text-muted mt-1 leading-relaxed">{toast.message}</p>
              )}
            </div>
            <button
              onClick={() => dismissToast(toast.id)}
              className="text-faint hover:text-ink p-0.5 rounded transition cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
};

