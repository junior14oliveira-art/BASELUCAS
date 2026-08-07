'use client';

import React, { useState } from 'react';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  Tabs,
  Tab,
  TextField,
  InputAdornment
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import FilterListIcon from '@mui/icons-material/FilterList';
import { Navbar } from '../../components/layout/Navbar';
import { Sidebar } from '../../components/layout/Sidebar';
import { AssistantDrawer } from '../../components/assistant/AssistantDrawer';

export default function ProductsPage() {
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const PRODUCTS = [
    {
      id: '100848229',
      sku: 'DELL3070MINI-I5-8TH-8G256',
      name: 'Mini Pc Dell 3070 Intel Core I5 - 8gb De Ram - 240gb - Excelente (Recondicionado)',
      cost: 0.00,
      price: 1999.00,
      stock: 0,
      channels: ['Mercado Livre (2)']
    },
    {
      id: '100481865',
      sku: 'DELL3070M-I3-9TH-8G120',
      name: 'Mini Pc Dell Optiplex 3070 Com Windows Intel Core I3 Memória Ram De 8gb Armazenamento De 120gb Preto',
      cost: 0.00,
      price: 2073.00,
      stock: 0,
      channels: ['Mercado Livre (1)', 'Shopee (1)']
    },
    {
      id: '100848229',
      sku: 'DELL-3070MINI-I5-9TH-8G256',
      name: 'Mini Pc Dell 3070 Intel Core I5 - 8gb De Ram - 240gb - Excelente (Recondicionado)',
      cost: 0.00,
      price: 2899.99,
      stock: 0,
      channels: ['Mercado Livre (1)']
    },
    {
      id: '101383773',
      sku: 'DELL3070MINI-I5-9TH-8G128',
      name: 'Dell Optiplex 3070',
      cost: 0.00,
      price: 1999.99,
      stock: 14,
      channels: ['Mercado Livre (1)', 'Amazon (1)']
    },
    {
      id: '101383775',
      sku: 'DELL3070MINI-I5-9TH-8G256',
      name: 'Dell 3070 127/220v Intel Core i5 8GB 256GB SSD',
      cost: 1200.00,
      price: 2199.00,
      stock: 8,
      channels: ['Mercado Livre (2)', 'Shopee (1)', 'Amazon (1)']
    }
  ];

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f8f9fc' }}>
      <Sidebar currentPath="/products" onNavigate={() => {}} />

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Navbar onToggleAssistant={() => setAssistantOpen(true)} />

        <Container maxWidth="xl" sx={{ mt: 3, mb: 4, flex: 1 }}>
          {/* Header Submenu Tabs (Matching BaseLinker Products Screen) */}
          <Paper elevation={0} sx={{ mb: 3, borderBottom: '1px solid #e1e2e5' }}>
            <Tabs value={activeTab} onChange={(e, val) => setActiveTab(val)} indicatorColor="primary">
              <Tab label="Produtos" fontWeight="bold" />
              <Tab label="Kits & Bundles" />
              <Tab label="Operações em Lote" />
              <Tab label="Promoções" />
              <Tab label="Controle de Inventário" />
            </Tabs>
          </Paper>

          {/* Action Toolbar */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <TextField
                size="small"
                placeholder="ID ou SKU contém..."
                sx={{ width: 300 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              <Button variant="outlined" startIcon={<FilterListIcon />}>
                Filtrar produtos
              </Button>
            </Box>

            <Button variant="contained" color="secondary" startIcon={<AddIcon />}>
              Adicionar produto
            </Button>
          </Box>

          {/* Products Data Table */}
          <Paper elevation={1} sx={{ borderRadius: 2 }}>
            <TableContainer>
              <Table size="small">
                <TableHead sx={{ backgroundColor: '#edeeef' }}>
                  <TableRow>
                    <TableCell padding="checkbox"><Checkbox size="small" /></TableCell>
                    <TableCell fontWeight="bold">Imagem / Título / ID / SKU</TableCell>
                    <TableCell fontWeight="bold" align="center">Estoque Unificado</TableCell>
                    <TableCell fontWeight="bold">Preço de Venda</TableCell>
                    <TableCell fontWeight="bold">Integrações Vinculadas</TableCell>
                    <TableCell fontWeight="bold" align="right">Ações</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {PRODUCTS.map((prod) => (
                    <TableRow key={prod.id} hover>
                      <TableCell padding="checkbox"><Checkbox size="small" /></TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Box sx={{ width: 40, height: 40, backgroundColor: '#edeef1', borderRadius: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            🖥️
                          </Box>
                          <Box>
                            <Typography variant="body2" fontWeight="bold" color="primary">
                              {prod.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              ID {prod.id} | SKU {prod.sku} | Custo: R$ {prod.cost.toFixed(2)}
                            </Typography>
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell align="center">
                        <Chip
                          label={`${prod.stock} un.`}
                          size="small"
                          color={prod.stock > 0 ? 'success' : 'default'}
                          sx={{ fontWeight: 'bold' }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {prod.price.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {prod.channels.map((ch, idx) => (
                            <Chip key={idx} label={ch} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />
                          ))}
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Button size="small" variant="text">Editar</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Container>

        <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} />
      </Box>
    </Box>
  );
}
