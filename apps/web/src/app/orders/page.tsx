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
  IconButton,
  TextField,
  InputAdornment
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import PrintIcon from '@mui/icons-material/Print';
import EmailIcon from '@mui/icons-material/Email';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import AddIcon from '@mui/icons-material/Add';
import FilterListIcon from '@mui/icons-material/FilterList';
import { Navbar } from '../../components/layout/Navbar';
import { Sidebar } from '../../components/layout/Sidebar';
import { OrderStatusSidebar } from '../../components/orders/OrderStatusSidebar';
import { AssistantDrawer } from '../../components/assistant/AssistantDrawer';

export default function OrdersPage() {
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState('Todos os pedidos');
  const [selectedOrders, setSelectedOrders] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');

  const ORDERS = [
    {
      id: '45267912',
      external_id: 'MLB-2000014408782989',
      marketplace: 'Mercado Livre',
      customer: 'Rennan Ruback de Mello',
      customer_handle: 'RENNANRUBACKDEMELLO',
      item: "1x Monitor Positivo 20' E2011px Para Pc Preto 127/220v",
      price: 447.00,
      status: 'Pedidos Agendados',
      shipping: 'ME2 - Mercado Envios Places',
      date: '07/08/2026 10:29'
    },
    {
      id: '45267159',
      external_id: 'MLB-2000014408793629',
      marketplace: 'Mercado Livre',
      customer: 'Gentil Dallo',
      customer_handle: 'GDALLO',
      item: '2x Notebook Hp Elitebook 15 8th 16gb Ssd 256gb W11 60hz Cor Prateado (Recondicionado)',
      price: 1899.99,
      status: 'Separação Tamires',
      shipping: 'ME2 - Mercado Envios Places',
      date: '07/08/2026 10:25'
    },
    {
      id: '45263649',
      external_id: 'MLB-2000014408421589',
      marketplace: 'Mercado Livre',
      customer: 'Luzia Tatiana Borges Smania de Oliveira',
      customer_handle: 'LUZIATATIANABORGESSMANIADE',
      item: '2x Monitor 19 LG Led Widescreen Preto Base Giratória (novo Com Caixa Aberta) 127/220v',
      price: 599.98,
      status: 'Separação Tamires',
      shipping: 'ME2 - Mercado Envios Places',
      date: '07/08/2026 10:01'
    },
    {
      id: '45263631',
      external_id: 'PERS-GL24',
      marketplace: 'Shopee',
      customer: 'Saulo Dias',
      customer_handle: 'saulo_dias',
      item: '20x Monitor Lenovo Tft 19.5 E2002b - Excelente (Recondicionado)',
      price: 20.00,
      status: 'Separação Meryellin',
      shipping: 'Pessoalmente / por telefone',
      date: '07/08/2026 10:02'
    },
    {
      id: '45261404',
      external_id: 'PERS-OPT3060',
      marketplace: 'Amazon',
      customer: 'GRANLESTE MOTORES LTDA',
      customer_handle: 'granleste_motores',
      item: '8x Mini Pc Dell Optiplex 3060 Intel Core I5 - 16gb De Ram - 240gb - Excelente',
      price: 15992.00,
      status: 'Pronto P/ Envio',
      shipping: 'Computador Geral',
      date: '07/08/2026 09:47'
    }
  ];

  const toggleSelectOrder = (id: string) => {
    setSelectedOrders(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const filteredOrders = ORDERS.filter(order => {
    if (selectedStatus !== 'Todos os pedidos' && order.status !== selectedStatus) {
      return false;
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        order.id.includes(term) ||
        order.customer.toLowerCase().includes(term) ||
        order.item.toLowerCase().includes(term)
      );
    }
    return true;
  });

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f8f9fc' }}>
      <Sidebar currentPath="/orders" onNavigate={() => {}} />

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Navbar onToggleAssistant={() => setAssistantOpen(true)} />

        <Box sx={{ display: 'flex', flex: 1 }}>
          {/* BaseLinker Workflow Status Sidebar */}
          <OrderStatusSidebar
            selectedStatus={selectedStatus}
            onSelectStatus={(status) => setSelectedStatus(status)}
          />

          {/* Main Orders Table Area */}
          <Box sx={{ flex: 1, p: 3 }}>
            {/* Action Bar Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Button variant="contained" color="primary" startIcon={<AddIcon />}>
                  Adicionar pedido
                </Button>
                <Typography variant="h6" fontWeight="bold" color="primary">
                  Todos os pedidos ({filteredOrders.length})
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <TextField
                  size="small"
                  placeholder="Filtros de pedidos..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon fontSize="small" />
                      </InputAdornment>
                    ),
                  }}
                  sx={{ width: 280 }}
                />
                <Button variant="outlined" startIcon={<FilterListIcon />}>
                  Filtros
                </Button>
              </Box>
            </Box>

            {/* High Density Orders Table */}
            <Paper elevation={1} sx={{ borderRadius: 2 }}>
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ backgroundColor: '#edeeef' }}>
                    <TableRow>
                      <TableCell padding="checkbox">
                        <Checkbox size="small" />
                      </TableCell>
                      <TableCell fontWeight="bold">Número</TableCell>
                      <TableCell fontWeight="bold">Nome / Sobrenome</TableCell>
                      <TableCell fontWeight="bold">Itens</TableCell>
                      <TableCell fontWeight="bold">Preço</TableCell>
                      <TableCell fontWeight="bold">Informações Adicionais (Método)</TableCell>
                      <TableCell fontWeight="bold">Data do Pedido (Em Status)</TableCell>
                      <TableCell fontWeight="bold" align="center">Ações</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filteredOrders.map((order) => {
                      const isSelected = selectedOrders.includes(order.id);
                      return (
                        <TableRow key={order.id} hover selected={isSelected}>
                          <TableCell padding="checkbox">
                            <Checkbox
                              size="small"
                              checked={isSelected}
                              onChange={() => toggleSelectOrder(order.id)}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight="bold" color="primary">
                              {order.id}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight="bold">{order.customer}</Typography>
                            <Typography variant="caption" color="text.secondary" display="block">
                              M ({order.customer_handle})
                            </Typography>
                          </TableCell>
                          <TableCell sx={{ maxWidth: 300 }}>
                            <Typography variant="body2" noWrap>{order.item}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight="bold">
                              R$ {order.price.toFixed(2)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={order.status}
                              size="small"
                              sx={{
                                fontWeight: 'bold',
                                backgroundColor:
                                  order.status.includes('Separação') ? '#9c27b0' :
                                  order.status.includes('Pronto') ? '#2e7d32' : '#ed6c02',
                                color: '#ffffff',
                                mb: 0.5
                              }}
                            />
                            <Typography variant="caption" display="block" color="text.secondary">
                              {order.shipping}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" display="block">{order.date}</Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                              <IconButton size="small"><StarBorderIcon fontSize="small" /></IconButton>
                              <IconButton size="small"><EmailIcon fontSize="small" /></IconButton>
                              <IconButton size="small"><PrintIcon fontSize="small" /></IconButton>
                              <IconButton size="small"><LocalOfferIcon fontSize="small" /></IconButton>
                            </Box>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* Floating Bulk Action Bar (Jakob Nielsen Heuristic 7) */}
            {selectedOrders.length > 0 && (
              <Paper
                elevation={6}
                sx={{
                  position: 'fixed',
                  bottom: 24,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  backgroundColor: '#1a237e',
                  color: '#ffffff',
                  px: 3,
                  py: 1.5,
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  zIndex: 1000,
                }}
              >
                <Typography variant="body2" fontWeight="bold">
                  {selectedOrders.length} pedido(s) selecionado(s)
                </Typography>
                <Button size="small" variant="contained" color="secondary">
                  Emitir NF-e em Lote
                </Button>
                <Button size="small" variant="outlined" sx={{ color: '#fff', borderColor: '#fff' }}>
                  Gerar Etiquetas Thermal
                </Button>
                <Button size="small" variant="outlined" sx={{ color: '#fff', borderColor: '#fff' }}>
                  Disparar WhatsApp
                </Button>
              </Paper>
            )}
          </Box>
        </Box>

        <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} />
      </Box>
    </Box>
  );
}
