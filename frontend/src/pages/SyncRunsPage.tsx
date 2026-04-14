import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  IconButton,
  Tooltip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  useTheme,
} from '@mui/material';
import {
  Refresh,
  ArrowBack,
  Info,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';
import { SyncRun } from '../types';

const statusConfig: Record<string, { color: 'success' | 'info' | 'error' | 'default' | 'warning'; label: string }> = {
  completed: { color: 'success', label: 'Concluido' },
  running: { color: 'info', label: 'Em execucao' },
  failed: { color: 'error', label: 'Falhou' },
  pending: { color: 'default', label: 'Pendente' },
  partial: { color: 'warning', label: 'Parcial' },
};

const SyncRunsPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { showError } = useNotification();

  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [providerFilter, setProviderFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [detailRun, setDetailRun] = useState<SyncRun | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    fetchRuns();
  }, [providerFilter]);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      const response = await apiService.getSyncRuns(providerFilter || undefined, 100);
      setRuns(response.data);
    } catch (error) {
      showError('Erro ao carregar historico de sincronizacoes');
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = async (run: SyncRun) => {
    try {
      setLoadingDetail(true);
      setDetailDialogOpen(true);
      const response = await apiService.getSyncRunDetail(run.id);
      setDetailRun(response.data);
    } catch (error) {
      setDetailRun(run);
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatDuration = (start: string, end: string | null): string => {
    if (!end) return 'Em andamento';
    const ms = new Date(end).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const uniqueProviders = Array.from(new Set(runs.map((r) => r.provider_name)));

  const filteredRuns = runs.filter((run) => {
    if (statusFilter && run.status !== statusFilter) return false;
    return true;
  });

  const getStatusChip = (status: string) => {
    const config = statusConfig[status] || { color: 'default' as const, label: status };
    return <Chip label={config.label} size="small" color={config.color} />;
  };

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Tooltip title="Voltar">
          <IconButton onClick={() => navigate('/sourcing')}>
            <ArrowBack />
          </IconButton>
        </Tooltip>
        <Box flexGrow={1}>
          <Typography variant="h4" fontWeight={700}>
            Historico de Sincronizacoes
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Acompanhe as execucoes de sincronizacao dos provedores
          </Typography>
        </Box>
        <Tooltip title="Atualizar">
          <IconButton onClick={fetchRuns}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Provedor</InputLabel>
          <Select
            value={providerFilter}
            onChange={(e) => setProviderFilter(e.target.value)}
            label="Provedor"
          >
            <MenuItem value="">Todos</MenuItem>
            {uniqueProviders.map((p) => (
              <MenuItem key={p} value={p}>
                {p}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Box display="flex" gap={0.5} flexWrap="wrap">
          <Chip
            label="Todos"
            size="small"
            variant={statusFilter === '' ? 'filled' : 'outlined'}
            onClick={() => setStatusFilter('')}
            color={statusFilter === '' ? 'primary' : 'default'}
          />
          {Object.entries(statusConfig).map(([key, config]) => (
            <Chip
              key={key}
              label={config.label}
              size="small"
              variant={statusFilter === key ? 'filled' : 'outlined'}
              onClick={() => setStatusFilter(statusFilter === key ? '' : key)}
              color={statusFilter === key ? config.color : 'default'}
            />
          ))}
        </Box>
      </Paper>

      {/* Table */}
      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={48} />
        </Box>
      ) : filteredRuns.length === 0 ? (
        <Box textAlign="center" py={8}>
          <Typography variant="h6" color="text.secondary">
            Nenhuma sincronizacao encontrada
          </Typography>
        </Box>
      ) : (
        <TableContainer component={Paper} sx={{ border: '1px solid', borderColor: 'divider' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Provider</TableCell>
                <TableCell>Tipo</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Inicio</TableCell>
                <TableCell>Duracao</TableCell>
                <TableCell align="right">Criados</TableCell>
                <TableCell align="right">Atualizados</TableCell>
                <TableCell align="right">Falhas</TableCell>
                <TableCell align="center">Detalhes</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredRuns.map((run) => (
                <TableRow
                  key={run.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => handleRowClick(run)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {run.provider_name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={run.run_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>{getStatusChip(run.status)}</TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {new Date(run.started_at).toLocaleString('pt-BR')}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDuration(run.started_at, run.finished_at)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="success.main" fontWeight={500}>
                      {run.total_created}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="info.main" fontWeight={500}>
                      {run.total_updated}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      color={run.total_failed > 0 ? 'error.main' : 'text.secondary'}
                      fontWeight={run.total_failed > 0 ? 600 : 400}
                    >
                      {run.total_failed}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton size="small">
                      <Info fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Detalhes da Sincronizacao
        </DialogTitle>
        <DialogContent>
          {loadingDetail ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress />
            </Box>
          ) : detailRun ? (
            <Box sx={{ pt: 1 }}>
              <Box display="flex" justifyContent="space-between" mb={2}>
                <Typography variant="subtitle2" color="text.secondary">
                  Provider
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  {detailRun.provider_name}
                </Typography>
              </Box>
              <Box display="flex" justifyContent="space-between" mb={2}>
                <Typography variant="subtitle2" color="text.secondary">
                  Tipo
                </Typography>
                <Chip label={detailRun.run_type} size="small" variant="outlined" />
              </Box>
              <Box display="flex" justifyContent="space-between" mb={2}>
                <Typography variant="subtitle2" color="text.secondary">
                  Status
                </Typography>
                {getStatusChip(detailRun.status)}
              </Box>
              <Box display="flex" justifyContent="space-between" mb={2}>
                <Typography variant="subtitle2" color="text.secondary">
                  Inicio
                </Typography>
                <Typography variant="body2">
                  {new Date(detailRun.started_at).toLocaleString('pt-BR')}
                </Typography>
              </Box>
              <Box display="flex" justifyContent="space-between" mb={2}>
                <Typography variant="subtitle2" color="text.secondary">
                  Duracao
                </Typography>
                <Typography variant="body2">
                  {formatDuration(detailRun.started_at, detailRun.finished_at)}
                </Typography>
              </Box>

              <Paper
                variant="outlined"
                sx={{ p: 2, mt: 2, bgcolor: 'background.default' }}
              >
                <Typography variant="subtitle2" gutterBottom>
                  Resultados
                </Typography>
                <Box display="flex" flexDirection="column" gap={1}>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body2">Total escaneados</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {detailRun.total_scanned}
                    </Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body2">Criados</Typography>
                    <Typography variant="body2" fontWeight={500} color="success.main">
                      {detailRun.total_created}
                    </Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body2">Atualizados</Typography>
                    <Typography variant="body2" fontWeight={500} color="info.main">
                      {detailRun.total_updated}
                    </Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body2">Inalterados</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {detailRun.total_unchanged}
                    </Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body2">Falhas</Typography>
                    <Typography
                      variant="body2"
                      fontWeight={500}
                      color={detailRun.total_failed > 0 ? 'error.main' : 'text.secondary'}
                    >
                      {detailRun.total_failed}
                    </Typography>
                  </Box>
                </Box>
              </Paper>

              {detailRun.error_detail && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {detailRun.error_detail}
                </Alert>
              )}
            </Box>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>Fechar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SyncRunsPage;
