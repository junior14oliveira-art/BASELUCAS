'use client';

import React, { useState } from 'react';
import { Box, Container, Typography, Paper } from '@mui/material';
import { Navbar } from '../../components/layout/Navbar';
import { Sidebar } from '../../components/layout/Sidebar';
import { IntegrationsTopologyMap } from '../../components/integrations/IntegrationsTopologyMap';
import { AssistantDrawer } from '../../components/assistant/AssistantDrawer';

export default function IntegrationsPage() {
  const [assistantOpen, setAssistantOpen] = useState(false);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f8f9fc' }}>
      <Sidebar currentPath="/integrations" onNavigate={() => {}} />

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Navbar onToggleAssistant={() => setAssistantOpen(true)} />

        <Container maxWidth="xl" sx={{ mt: 3, mb: 4, flex: 1 }}>
          <Paper elevation={0} sx={{ p: 2, mb: 3, borderBottom: '1px solid #e1e2e5' }}>
            <Typography variant="h5" fontWeight="bold" color="primary">
              Mapa de Topologia de Integrações (Base.com Spec)
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Gerencie múltiplas contas de marketplaces (Mercado Livre, Shopee, Amazon), Bling ERPs, SEFAZ e o daemon de impressão remota local.
            </Typography>
          </Paper>

          <IntegrationsTopologyMap />
        </Container>

        <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} />
      </Box>
    </Box>
  );
}
