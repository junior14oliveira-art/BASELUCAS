import React from 'react';
import { Box, Paper, Typography, Grid, Chip, Button } from '@mui/material';
import HubIcon from '@mui/icons-material/Hub';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

interface IntegrationNode {
  name: str;
  subLabel: str;
  category: 'MARKETPLACE' | 'LOGISTICS' | 'ERP' | 'DAEMON' | 'FISCAL';
  icon: str;
}

const INTEGRATIONS: IntegrationNode[] = [
  { name: 'Mercado Livre', subLabel: 'Portal da informática ...', category: 'MARKETPLACE', icon: '🟡' },
  { name: 'Mercado Livre', subLabel: '4M&C INFORMÁTICA E...', category: 'MARKETPLACE', icon: '🟡' },
  { name: 'Mercado Livre', subLabel: '4MC MAX INFORMATI...', category: 'MARKETPLACE', icon: '🟡' },
  { name: 'Mercado Livre', subLabel: 'STAR LUDE INFORMAT...', category: 'MARKETPLACE', icon: '🟡' },
  { name: 'Mercado Livre', subLabel: 'Mali brasil MEVCGRZZ', category: 'MARKETPLACE', icon: '🟡' },
  { name: 'Mercado Envios', subLabel: 'PORTAL', category: 'LOGISTICS', icon: '🟢' },
  { name: 'Mercado Envios', subLabel: 'MAX', category: 'LOGISTICS', icon: '🟢' },
  { name: 'Mercado Envios', subLabel: '4M&C', category: 'LOGISTICS', icon: '🟢' },
  { name: 'Bling ERP', subLabel: 'Bling Portal', category: 'ERP', icon: '🟢' },
  { name: 'Bling ERP', subLabel: 'Bling Max', category: 'ERP', icon: '🟢' },
  { name: 'Bling ERP', subLabel: 'Bling 4M&C', category: 'ERP', icon: '🟢' },
  { name: 'Bling ERP', subLabel: 'Bling Brasil', category: 'ERP', icon: '🟢' },
  { name: 'SEFAZ (beta)', subLabel: 'SEFAZ (ERP)', category: 'FISCAL', icon: '📄' },
];

export const IntegrationsTopologyMap: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      {/* Master Hub Node */}
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 4 }}>
        <Paper
          elevation={3}
          sx={{
            px: 4,
            py: 2,
            backgroundColor: '#1a237e',
            color: '#ffffff',
            borderRadius: 3,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <HubIcon fontSize="large" color="secondary" />
          <Typography variant="h5" fontWeight="bold">
            base.ai mestre
          </Typography>
        </Paper>
        <Box sx={{ width: 2, height: 30, backgroundColor: '#1a237e', my: 1 }} />
      </Box>

      {/* Connected Integrations Grid */}
      <Grid container spacing={2}>
        {INTEGRATIONS.map((node, index) => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={index}>
            <Paper
              elevation={1}
              sx={{
                p: 2,
                borderRadius: 2,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                border: '1px solid #e1e2e5',
                '&:hover': { boxShadow: '0px 4px 12px rgba(26, 35, 126, 0.15)', borderColor: '#1a237e' },
              }}
            >
              <Typography variant="h4" sx={{ mb: 1 }}>
                {node.icon}
              </Typography>
              <Typography variant="subtitle1" fontWeight="bold" color="primary">
                {node.name}
              </Typography>
              <Chip
                label={node.subLabel}
                size="small"
                variant="outlined"
                sx={{ mt: 1, fontSize: '0.75rem', fontWeight: 600 }}
              />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1.5 }}>
                <CheckCircleIcon color="success" sx={{ fontSize: 14 }} />
                <Typography variant="caption" color="text.secondary" fontWeight="bold">
                  Conectado & Sincronizado
                </Typography>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* Base Printer Daemon Node */}
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mt: 4 }}>
        <Box sx={{ width: 2, height: 30, backgroundColor: '#1a237e', my: 1 }} />
        <Paper
          elevation={2}
          sx={{
            px: 3,
            py: 1.5,
            backgroundColor: '#ffffff',
            border: '2px solid #008080',
            borderRadius: 3,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <Typography variant="subtitle1" fontWeight="bold" color="secondary">
            🖨️ base.printer daemon
          </Typography>
          <Chip label="Base Printer Local: Online" color="success" size="small" />
        </Paper>

        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          sx={{ mt: 3, borderRadius: 4, px: 3 }}
        >
          Adicionar Nova Integração
        </Button>
      </Box>
    </Box>
  );
};
