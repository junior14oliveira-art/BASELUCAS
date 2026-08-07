import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  InputBase,
  Badge,
  Box,
  Button,
  Chip,
  Menu,
  MenuItem,
  Paper
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import NotificationsIcon from '@mui/icons-material/Notifications';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SyncIcon from '@mui/icons-material/Sync';
import PrintIcon from '@mui/icons-material/Print';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';

interface NavbarProps {
  onToggleAssistant: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleAssistant }) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [selectedChannel, setSelectedChannel] = React.useState('Todos os Canais');

  const handleOpenChannelMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleSelectChannel = (channel: str) => {
    setSelectedChannel(channel);
    setAnchorEl(null);
  };

  return (
    <AppBar position="sticky" elevation={1} sx={{ backgroundColor: '#ffffff', color: '#1a237e', borderBottom: '1px solid #e1e2e5' }}>
      <Toolbar variant="dense" sx={{ justifyContent: 'space-between', gap: 2 }}>
        {/* Brand Logo & Channel Switcher */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6" fontWeight="bold" sx={{ background: 'linear-gradient(45deg, #1a237e, #008080)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            base.ai
          </Typography>

          <Button
            size="small"
            variant="outlined"
            onClick={handleOpenChannelMenu}
            sx={{ borderColor: '#e1e2e5', color: '#1a237e', textTransform: 'none', fontWeight: 600 }}
          >
            🛒 {selectedChannel} ▾
          </Button>
          <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
            <MenuItem onClick={() => handleSelectChannel('Todos os Canais')}>Todos os Canais</MenuItem>
            <MenuItem onClick={() => handleSelectChannel('Mercado Livre')}>Mercado Livre</MenuItem>
            <MenuItem onClick={() => handleSelectChannel('Shopee')}>Shopee</MenuItem>
            <MenuItem onClick={() => handleSelectChannel('Amazon')}>Amazon</MenuItem>
            <MenuItem onClick={() => handleSelectChannel('Bling ERP')}>Bling ERP</MenuItem>
          </Menu>
        </Box>

        {/* Global Search Bar (Nielsen Heuristic 6) */}
        <Paper
          component="form"
          sx={{ display: 'flex', alignItems: 'center', width: 450, px: 1.5, py: 0.5, backgroundColor: '#f2f3f6', borderRadius: 2, boxShadow: 'none' }}
        >
          <SearchIcon sx={{ color: '#767683', mr: 1 }} />
          <InputBase
            placeholder="Buscar pedidos, SKUs, clientes, rastreamento... (Ctrl + K)"
            sx={{ ml: 1, flex: 1, fontSize: '0.875rem' }}
          />
        </Paper>

        {/* Right Action Icons & Status Indicators */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          {/* Base Printer Status */}
          <Chip
            icon={<PrintIcon sx={{ fontSize: 16 }} />}
            label="Base.printer: Online"
            size="small"
            color="success"
            variant="outlined"
            sx={{ fontSize: '0.75rem', fontWeight: 600 }}
          />

          {/* Sync Queue Pulse Indicator (Nielsen Heuristic 1) */}
          <Chip
            icon={<SyncIcon sx={{ fontSize: 16, animation: 'spin 3s linear infinite' }} />}
            label="Filas: OK"
            size="small"
            sx={{ backgroundColor: '#e0e0ff', color: '#000767', fontSize: '0.75rem', fontWeight: 600 }}
          />

          <IconButton size="small" color="inherit">
            <Badge badgeContent={3} color="error">
              <NotificationsIcon fontSize="small" />
            </Badge>
          </IconButton>

          {/* AI Assistant Drawer Trigger */}
          <Button
            variant="contained"
            color="secondary"
            size="small"
            startIcon={<SmartToyIcon />}
            onClick={onToggleAssistant}
            sx={{ borderRadius: 4, px: 2 }}
          >
            Assistente IA
          </Button>

          <IconButton size="small" color="inherit">
            <AccountCircleIcon />
          </IconButton>
        </Box>
      </Toolbar>
    </AppBar>
  );
};
