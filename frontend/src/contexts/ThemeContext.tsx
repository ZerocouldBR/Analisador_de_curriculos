import React, { createContext, useContext, useState, useMemo, ReactNode } from 'react';
import { createTheme, ThemeProvider as MuiThemeProvider, Theme } from '@mui/material';

interface ThemeContextType {
  mode: 'light' | 'dark';
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useThemeMode = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeMode must be used within a ThemeContextProvider');
  }
  return context;
};

const getDesignTokens = (mode: 'light' | 'dark') => ({
  palette: {
    mode,
    ...(mode === 'light'
      ? {
          primary: { main: '#1565c0', light: '#1976d2', dark: '#0d47a1' },
          secondary: { main: '#7b1fa2', light: '#9c27b0', dark: '#4a148c' },
          background: { default: '#f5f7fa', paper: '#ffffff' },
          success: { main: '#2e7d32' },
          warning: { main: '#ed6c02' },
          info: { main: '#0288d1' },
        }
      : {
          primary: { main: '#90caf9', light: '#bbdefb', dark: '#42a5f5' },
          secondary: { main: '#ce93d8', light: '#f3e5f5', dark: '#ab47bc' },
          background: { default: '#121212', paper: '#1e1e1e' },
          success: { main: '#66bb6a' },
          warning: { main: '#ffa726' },
          info: { main: '#29b6f6' },
        }),
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none' as const,
          fontWeight: 500,
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
      defaultProps: {
        elevation: 0,
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: mode === 'light' ? '1px solid #e0e0e0' : '1px solid #333',
          boxShadow: mode === 'light'
            ? '0 1px 3px rgba(0,0,0,0.08)'
            : '0 1px 3px rgba(0,0,0,0.3)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          boxShadow: mode === 'light'
            ? '0 1px 3px rgba(0,0,0,0.1)'
            : '0 1px 3px rgba(0,0,0,0.4)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderRight: mode === 'light' ? '1px solid #e0e0e0' : '1px solid #333',
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined' as const,
        size: 'small' as const,
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: 'none',
          '& .MuiDataGrid-cell:focus': {
            outline: 'none',
          },
          '& .MuiDataGrid-columnHeader:focus': {
            outline: 'none',
          },
        },
      },
    },
  },
});

interface ThemeContextProviderProps {
  children: ReactNode;
}

export const ThemeContextProvider: React.FC<ThemeContextProviderProps> = ({ children }) => {
  const [mode, setMode] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme_mode');
    return (saved as 'light' | 'dark') || 'light';
  });

  const toggleTheme = () => {
    setMode((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      localStorage.setItem('theme_mode', next);
      return next;
    });
  };

  const theme = useMemo(() => createTheme(getDesignTokens(mode)), [mode]);

  return (
    <ThemeContext.Provider value={{ mode, toggleTheme }}>
      <MuiThemeProvider theme={theme}>{children}</MuiThemeProvider>
    </ThemeContext.Provider>
  );
};
