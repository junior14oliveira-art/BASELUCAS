import { createTheme } from '@mui/material/styles';

export const md3Theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#2563eb', // Deep Electric Blue (Portal One)
      light: '#60a5fa',
      dark: '#1d4ed8',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#06b6d4', // Tech Cyan (Portal One)
      light: '#67e8f9',
      dark: '#0891b2',
      contrastText: '#ffffff',
    },
    background: {
      default: '#051424',
      paper: '#0f172a',
    },
    text: {
      primary: '#d4e4fa',
      secondary: '#8d90a0',
    },
    error: {
      main: '#f43f5e',
    },
    warning: {
      main: '#f59e0b',
    },
    success: {
      main: '#10b981',
    },
    info: {
      main: '#06b6d4',
    },
  },
  typography: {
    fontFamily: '"Inter", "JetBrains Mono", sans-serif',
    h5: {
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h6: {
      fontWeight: 700,
    },
    subtitle1: {
      fontWeight: 600,
    },
    body1: {
      fontSize: '0.9rem',
    },
    body2: {
      fontSize: '0.825rem',
    },
    button: {
      textTransform: 'none',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          padding: '8px 16px',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#122131',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
        },
      },
    },
  },
});
