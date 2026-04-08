import React, { createContext, useContext, useCallback, ReactNode } from 'react';
import { SnackbarProvider, useSnackbar, VariantType } from 'notistack';

interface NotificationContextType {
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
  showWarning: (message: string) => void;
  showInfo: (message: string) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};

const NotificationInner: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { enqueueSnackbar } = useSnackbar();

  const show = useCallback(
    (message: string, variant: VariantType) => {
      enqueueSnackbar(message, {
        variant,
        anchorOrigin: { vertical: 'bottom', horizontal: 'right' },
        autoHideDuration: 4000,
      });
    },
    [enqueueSnackbar]
  );

  const value: NotificationContextType = {
    showSuccess: useCallback((msg: string) => show(msg, 'success'), [show]),
    showError: useCallback((msg: string) => show(msg, 'error'), [show]),
    showWarning: useCallback((msg: string) => show(msg, 'warning'), [show]),
    showInfo: useCallback((msg: string) => show(msg, 'info'), [show]),
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

export const NotificationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <SnackbarProvider maxSnack={3} dense>
      <NotificationInner>{children}</NotificationInner>
    </SnackbarProvider>
  );
};
