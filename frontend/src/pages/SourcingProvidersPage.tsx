import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  Alert,
  Tooltip,
  IconButton,
  Divider,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Refresh,
  PlayArrow,
  Settings,
  CheckCircle,
  Cancel,
  Hub,
  History,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';
import { SourcingProvider, ProviderStatus } from '../types';

const SourcingProvidersPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { showSuccess, showError, showInfo } = useNotification();

  const [providers, setProviders] = useState<SourcingProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [testResults, setTestResults] = useState<Record<string, ProviderStatus | null>>({});
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);

  // Config dialog state
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [configProvider, setConfigProvider] = useState<SourcingProvider | null>(null);
  const [configForm, setConfigForm] = useState({
    is_enabled: false,
    schedule_cron: '',
    rate_limit_rpm: 60,
    rate_limit_daily: 1000,
  });
  const [savingConfig, setSavingConfig] = useState(false);

  useEffect(() => {
    fetchProviders();
  }, []);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const response = await apiService.getSourcingProviders();
      setProviders(response.data);
    } catch (error) {
      showError('Erro ao carregar provedores de sourcing');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async (providerName: string) => {
    try {
      setTestingProvider(providerName);
      const response = await apiService.testProvider(providerName);
      const status: ProviderStatus = response.data;
      setTestResults((prev) => ({ ...prev, [providerName]: status }));
      if (status.healthy) {
        showSuccess(`${providerName}: Conexao bem-sucedida`);
      } else {
        showError(`${providerName}: ${status.message}`);
      }
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Erro ao testar conexao';
      setTestResults((prev) => ({
        ...prev,
        [providerName]: { provider_name: providerName, healthy: false, message: msg, remaining_quota: null },
      }));
      showError(msg);
    } finally {
      setTestingProvider(null);
    }
  };

  const handleSync = async (providerName: string) => {
    try {
      setSyncingProvider(providerName);
      await apiService.triggerSync(providerName);
      showSuccess(`Sincronizacao iniciada para ${providerName}`);
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao iniciar sincronizacao');
    } finally {
      setSyncingProvider(null);
    }
  };

  const openConfigDialog = (provider: SourcingProvider) => {
    setConfigProvider(provider);
    setConfigForm({
      is_enabled: provider.is_enabled,
      schedule_cron: '',
      rate_limit_rpm: 60,
      rate_limit_daily: 1000,
    });
    setConfigDialogOpen(true);
  };

  const handleSaveConfig = async () => {
    if (!configProvider) return;
    try {
      setSavingConfig(true);
      await apiService.upsertProviderConfig({
        provider_name: configProvider.name,
        is_enabled: configForm.is_enabled,
        schedule_cron: configForm.schedule_cron || null,
        rate_limit_rpm: configForm.rate_limit_rpm,
        rate_limit_daily: configForm.rate_limit_daily,
      });
      showSuccess('Configuracao salva com sucesso');
      setConfigDialogOpen(false);
      fetchProviders();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao salvar configuracao');
    } finally {
      setSavingConfig(false);
    }
  };

  const getTypeColor = (type: string): 'primary' | 'secondary' | 'warning' | 'info' | 'default' => {
    switch (type.toLowerCase()) {
      case 'ats': return 'primary';
      case 'social': return 'info';
      case 'job_board': return 'secondary';
      case 'internal': return 'warning';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress size={48} />
      </Box>
    );
  }

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Sourcing Providers
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Gerencie provedores de sourcing hibrido de candidatos
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<History />}
            onClick={() => navigate('/sourcing/runs')}
          >
            Historico de Syncs
          </Button>
          <Tooltip title="Atualizar">
            <IconButton onClick={fetchProviders}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {providers.length === 0 ? (
        <Box textAlign="center" py={8}>
          <Hub sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            Nenhum provedor configurado
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Configure provedores de sourcing no backend para comecar
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={3}>
          {providers.map((provider) => {
            const testResult = testResults[provider.name];
            return (
              <Grid item xs={12} sm={6} md={4} key={provider.name}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    border: '1px solid',
                    borderColor: 'divider',
                    transition: 'box-shadow 0.2s',
                    '&:hover': { boxShadow: 4 },
                  }}
                >
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                      <Typography variant="h6" fontWeight={600}>
                        {provider.name}
                      </Typography>
                      <Chip
                        label={provider.type}
                        size="small"
                        color={getTypeColor(provider.type)}
                        variant="outlined"
                      />
                    </Box>

                    <Box display="flex" gap={1} mb={2} flexWrap="wrap">
                      <Chip
                        icon={provider.is_configured ? <CheckCircle /> : <Cancel />}
                        label={provider.is_configured ? 'Configurado' : 'Nao configurado'}
                        size="small"
                        color={provider.is_configured ? 'success' : 'default'}
                        variant="outlined"
                      />
                      <Chip
                        icon={provider.is_enabled ? <CheckCircle /> : <Cancel />}
                        label={provider.is_enabled ? 'Ativo' : 'Inativo'}
                        size="small"
                        color={provider.is_enabled ? 'success' : 'default'}
                        variant="outlined"
                      />
                    </Box>

                    <Typography variant="caption" color="text.secondary" display="block">
                      Ultimo sync:{' '}
                      {provider.last_sync_at
                        ? new Date(provider.last_sync_at).toLocaleString('pt-BR')
                        : 'Nunca'}
                    </Typography>

                    {/* Test result inline */}
                    {testResult && (
                      <Alert
                        severity={testResult.healthy ? 'success' : 'error'}
                        sx={{ mt: 2 }}
                        variant="outlined"
                        onClose={() =>
                          setTestResults((prev) => ({ ...prev, [provider.name]: null }))
                        }
                      >
                        {testResult.message}
                        {testResult.remaining_quota !== null && (
                          <Typography variant="caption" display="block">
                            Cota restante: {testResult.remaining_quota}
                          </Typography>
                        )}
                      </Alert>
                    )}
                  </CardContent>

                  <Divider />

                  <CardActions sx={{ px: 2, py: 1.5, justifyContent: 'space-between' }}>
                    <Button
                      size="small"
                      onClick={() => handleTest(provider.name)}
                      disabled={testingProvider === provider.name}
                      startIcon={
                        testingProvider === provider.name ? (
                          <CircularProgress size={16} />
                        ) : undefined
                      }
                    >
                      Testar Conexao
                    </Button>
                    <Box display="flex" gap={0.5}>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => handleSync(provider.name)}
                        disabled={!provider.is_enabled || syncingProvider === provider.name}
                        startIcon={
                          syncingProvider === provider.name ? (
                            <CircularProgress size={16} color="inherit" />
                          ) : (
                            <PlayArrow />
                          )
                        }
                      >
                        Sincronizar
                      </Button>
                      <Tooltip title="Configurar">
                        <IconButton size="small" onClick={() => openConfigDialog(provider)}>
                          <Settings fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </CardActions>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Config Dialog */}
      <Dialog
        open={configDialogOpen}
        onClose={() => setConfigDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Configurar {configProvider?.name}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={configForm.is_enabled}
                  onChange={(e) =>
                    setConfigForm((prev) => ({ ...prev, is_enabled: e.target.checked }))
                  }
                />
              }
              label="Provedor ativo"
            />
            <TextField
              label="Schedule (Cron)"
              value={configForm.schedule_cron}
              onChange={(e) =>
                setConfigForm((prev) => ({ ...prev, schedule_cron: e.target.value }))
              }
              placeholder="0 */6 * * *"
              helperText="Expressao cron para sincronizacao automatica (ex: 0 */6 * * *)"
              fullWidth
              size="small"
            />
            <TextField
              label="Rate Limit (req/min)"
              type="number"
              value={configForm.rate_limit_rpm}
              onChange={(e) =>
                setConfigForm((prev) => ({
                  ...prev,
                  rate_limit_rpm: parseInt(e.target.value) || 0,
                }))
              }
              fullWidth
              size="small"
            />
            <TextField
              label="Rate Limit (req/dia)"
              type="number"
              value={configForm.rate_limit_daily}
              onChange={(e) =>
                setConfigForm((prev) => ({
                  ...prev,
                  rate_limit_daily: parseInt(e.target.value) || 0,
                }))
              }
              fullWidth
              size="small"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleSaveConfig}
            disabled={savingConfig}
            startIcon={savingConfig ? <CircularProgress size={16} /> : undefined}
          >
            Salvar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SourcingProvidersPage;
