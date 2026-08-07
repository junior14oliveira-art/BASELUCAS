import React from 'react';
import { Box, Typography, List, ListItemButton, ListItemText, Chip, Divider } from '@mui/material';

interface OrderStatusSidebarProps {
  selectedStatus: string;
  onSelectStatus: (status: string) => void;
}

const WORKFLOW_SECTIONS = [
  {
    title: 'SEPARAÇÃO',
    items: [
      { name: 'Separação Caroline', count: 12, color: '#9c27b0' },
      { name: 'Separação Cláudio', count: 8, color: '#9c27b0' },
      { name: 'Separação Gledson', count: 5, color: '#9c27b0' },
      { name: 'Separação Letícia', count: 14, color: '#9c27b0' },
      { name: 'Separação Meryellin', count: 3, color: '#9c27b0' },
      { name: 'Separação Tamires', count: 9, color: '#9c27b0' },
      { name: 'Separação Finalizada', count: 45, color: '#673ab7' },
    ],
  },
  {
    title: 'EXPEDIÇÃO',
    items: [
      { name: 'Pronto P/ Envio', count: 70, color: '#2e7d32' },
      { name: 'Enviado', count: 5620, color: '#0288d1' },
    ],
  },
  {
    title: 'FATURAMENTO & FISCAL',
    items: [
      { name: 'Aguardando Faturamento', count: 0, color: '#ed6c02' },
      { name: 'NF Recebida', count: 2, color: '#2e7d32' },
      { name: 'Erro Enviar NF -> Plataforma', count: 1, color: '#d32f2f' },
    ],
  },
  {
    title: 'CATEGORIAS DE PRODUTOS',
    items: [
      { name: 'NOTEBOOKS', count: 26, color: '#008080' },
      { name: 'COMPUTADORES', count: 14, color: '#008080' },
      { name: 'MONITORES', count: 40, color: '#008080' },
    ],
  },
];

export const OrderStatusSidebar: React.FC<OrderStatusSidebarProps> = ({
  selectedStatus,
  onSelectStatus,
}) => {
  return (
    <Box
      sx={{
        width: 260,
        backgroundColor: '#ffffff',
        borderRight: '1px solid #e1e2e5',
        p: 1.5,
        height: 'calc(100vh - 56px)',
        overflowY: 'auto',
      }}
    >
      <Typography variant="subtitle2" fontWeight="bold" sx={{ px: 1, pb: 1, color: '#1a237e' }}>
        Status & Fluxos de Trabalho
      </Typography>

      <ListItemButton
        selected={selectedStatus === 'Todos os pedidos'}
        onClick={() => onSelectStatus('Todos os pedidos')}
        sx={{ borderRadius: 1.5, mb: 1, '&.Mui-selected': { backgroundColor: '#1a237e', color: '#fff' } }}
      >
        <ListItemText primary="Todos os pedidos" primaryTypographyProps={{ fontSize: '0.85rem', fontWeight: 'bold' }} />
        <Chip label="5756" size="small" sx={{ height: 18, fontSize: '0.7rem', fontWeight: 'bold' }} />
      </ListItemButton>

      <Divider sx={{ my: 1 }} />

      {WORKFLOW_SECTIONS.map((section, idx) => (
        <Box key={idx} sx={{ mb: 2 }}>
          <Typography variant="caption" fontWeight="bold" sx={{ px: 1, color: '#767683', letterSpacing: 0.5 }}>
            {section.title}
          </Typography>
          <List variant="dense" disablePadding sx={{ mt: 0.5 }}>
            {section.items.map((item) => {
              const isSel = selectedStatus === item.name;
              return (
                <ListItemButton
                  key={item.name}
                  selected={isSel}
                  onClick={() => onSelectStatus(item.name)}
                  sx={{
                    borderRadius: 1.5,
                    py: 0.4,
                    px: 1,
                    my: 0.1,
                    '&.Mui-selected': {
                      backgroundColor: '#edeef1',
                      fontWeight: 'bold',
                      borderLeft: `4px solid ${item.color}`,
                    },
                  }}
                >
                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: item.color, mr: 1 }} />
                  <ListItemText
                    primary={item.name}
                    primaryTypographyProps={{ fontSize: '0.8rem', noWrap: true }}
                  />
                  <Chip
                    label={item.count}
                    size="small"
                    sx={{
                      height: 16,
                      fontSize: '0.65rem',
                      backgroundColor: item.color,
                      color: '#ffffff',
                      fontWeight: 'bold',
                    }}
                  />
                </ListItemButton>
              );
            })}
          </List>
        </Box>
      ))}
    </Box>
  );
};
