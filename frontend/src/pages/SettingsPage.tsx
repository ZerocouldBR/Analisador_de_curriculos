import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Chip,
  Card,
  CardContent,
  Grid,
  Tab,
  Tabs,
  IconButton,
  Tooltip,
  Alert,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  FormHelperText,
  InputAdornment,
  useTheme,
  Snackbar,
  CircularProgress,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Memory,
  Storage,
  Security,
  Refresh,
  CheckCircle,
  Warning,
  Save,
  RestartAlt,
  Psychology,
  Hub,
  Chat,
  Search,
  WorkOutline,
  DocumentScanner,
  ViewModule,
  CloudUpload,
  AttachMoney,
  LinkedIn,
  Visibility,
  VisibilityOff,
  Info,
  DeleteForever,
  CleaningServices,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import {
  HealthCheck,
  SystemConfigResponse,
  SystemConfigCategory,
  SystemConfigField,
} from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { TableSkeleton } from '../components/LoadingSkeleton';

// Map icon names to MUI icon components
const iconMap: Record<string, React.ReactElement> = {
  Settings: <SettingsIcon />,
  Storage: <Storage />,
  Memory: <Memory />,
  Psychology: <Psychology />,
  Hub: <Hub />,
  Chat: <Chat />,
  Search: <Search />,
  WorkOutline: <WorkOutline />,
  DocumentScanner: <DocumentScanner />,
  ViewModule: <ViewModule />,
  CloudUpload: <CloudUpload />,
  Security: <Security />,
  AttachMoney: <AttachMoney />,
  LinkedIn: <LinkedIn />,
};

// Field renderer component
const ConfigFieldRenderer: React.FC<{
  field: SystemConfigField;
  value: any;
  onChange: (key: string, value: any) => void;
}> = ({ field, value, onChange }) => {
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (newValue: any) => {
    onChange(field.key, newValue);
  };

  switch (field.type) {
    case 'boolean':
      return (
        <FormControlLabel
          control={
            <Switch
              checked={!!value}
              onChange={(e) => handleChange(e.target.checked)}
              color="primary"
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight={500}>
                {field.label}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {field.description}
              </Typography>
            </Box>
          }
          sx={{ ml: 0, width: '100%', alignItems: 'flex-start' }}
        />
      );

    case 'select':
      return (
        <FormControl fullWidth size="small">
          <InputLabel>{field.label}</InputLabel>
          <Select
            value={value ?? ''}
            label={field.label}
            onChange={(e) => handleChange(e.target.value)}
          >
            {(field.options || []).map((opt) => (
              <MenuItem key={opt} value={opt}>
                {opt}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>{field.description}</FormHelperText>
        </FormControl>
      );

    case 'password':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          type={showPassword ? 'text' : 'password'}
          value={value ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={field.description}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={() => setShowPassword(!showPassword)}
                  edge="end"
                >
                  {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      );

    case 'number':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          type="number"
          value={value ?? ''}
          onChange={(e) => {
            const v = e.target.value;
            if (v === '') {
              handleChange('');
              return;
            }
            handleChange(
              field.step !== undefined && field.step < 1
                ? parseFloat(v)
                : parseInt(v, 10)
            );
          }}
          inputProps={{
            min: field.min_value,
            max: field.max_value,
            step: field.step,
          }}
          placeholder={field.placeholder}
          helperText={field.description}
        />
      );

    case 'textarea':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          multiline
          rows={4}
          value={value ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={field.description}
        />
      );

    case 'list_int':
    case 'list_str':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          value={Array.isArray(value) ? value.join(', ') : (value ?? '')}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={`${field.description} (separe com virgula)`}
        />
      );

    default: // text
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          value={value ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={field.description}
        />
      );
  }
};

const SettingsPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState(0);
  const [health, setHealth] = useState<HealthCheck | null>(null);

  // System config state
  const [config, setConfig] = useState<SystemConfigResponse | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, any>>({});
  const [hasChanges, setHasChanges] = useState(false);

  // Confirm dialogs
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [restartWarningOpen, setRestartWarningOpen] = useState(false);
  const [pendingSave, setPendingSave] = useState<Record<string, any> | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiService.getSystemConfig();
      setConfig(data);
      // Initialize edited values from current config
      const initial: Record<string, any> = {};
      data.categories.forEach((cat) => {
        cat.fields.forEach((field) => {
          initial[field.key] = field.value;
        });
      });
      setEditedValues(initial);
      setHasChanges(false);
    } catch (error) {
      showError('Erro ao carregar configuracoes do sistema');
    } finally {
      setLoading(false);
    }
  }, [showError]);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await apiService.healthCheck();
      setHealth(data);
    } catch (error) {
      console.error('Health check failed:', error);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchHealth();
  }, [fetchConfig, fetchHealth]);

  const handleFieldChange = (key: string, value: any) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const getChangedValues = (): Record<string, any> => {
    if (!config) return {};
    const changes: Record<string, any> = {};
    config.categories.forEach((cat) => {
      cat.fields.forEach((field) => {
        const original = field.value;
        const edited = editedValues[field.key];
        if (JSON.stringify(original) !== JSON.stringify(edited)) {
          changes[field.key] = edited;
        }
      });
    });
    return changes;
  };

  const hasRestartRequiredChanges = (): boolean => {
    if (!config) return false;
    const changes = getChangedValues();
    for (const key of Object.keys(changes)) {
      for (const cat of config.categories) {
        for (const field of cat.fields) {
          if (field.key === key && field.restart_required) {
            return true;
          }
        }
      }
    }
    return false;
  };

  const handleSave = async () => {
    const changes = getChangedValues();
    if (Object.keys(changes).length === 0) {
      showError('Nenhuma alteracao para salvar');
      return;
    }

    // Check if any changes require restart
    if (hasRestartRequiredChanges()) {
      setPendingSave(changes);
      setRestartWarningOpen(true);
      return;
    }

    await doSave(changes);
  };

  const doSave = async (values: Record<string, any>) => {
    try {
      setSaving(true);
      const result = await apiService.updateSystemConfig(values);
      showSuccess(
        `${result.updated_keys.length} configuracao(oes) atualizada(s)` +
        (result.restart_required ? '. Reinicie os servicos para aplicar todas as mudancas.' : '')
      );
      await fetchConfig();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao salvar configuracoes');
    } finally {
      setSaving(false);
      setRestartWarningOpen(false);
      setPendingSave(null);
    }
  };

  const handleReset = async () => {
    try {
      await apiService.resetSystemConfig();
      showSuccess('Configuracoes restauradas aos valores padrao. Reinicie os servicos.');
      setResetDialogOpen(false);
      await fetchConfig();
    } catch (error) {
      showError('Erro ao restaurar configuracoes');
    }
  };

  const StatusChip = ({ status }: { status?: string }) => {
    if (!status) return null;
    const isOk = status === 'ok' || status === 'healthy' || status === 'connected';
    return (
      <Chip
        icon={isOk ? <CheckCircle /> : <Warning />}
        label={status}
        size="small"
        color={isOk ? 'success' : 'warning'}
        variant="outlined"
      />
    );
  };

  if (loading) return <TableSkeleton />;

  const categories = config?.categories || [];
  // Tab indices
  const healthTabIndex = categories.length;
  const databaseTabIndex = categories.length + 1;

  // Database management state
  const [dbStats, setDbStats] = useState<any>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [clearOptions, setClearOptions] = useState({
    clear_candidates: true,
    clear_documents: true,
    clear_conversations: false,
    clear_audit_logs: false,
    clear_ai_usage: false,
    reset_sequences: true,
  });
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearResult, setClearResult] = useState<any>(null);

  const fetchDbStats = useCallback(async () => {
    setDbLoading(true);
    try {
      const stats = await apiService.getDatabaseStats();
      setDbStats(stats);
    } catch (error) {
      console.error('Failed to fetch DB stats:', error);
    } finally {
      setDbLoading(false);
    }
  }, []);

  const handleClearDatabase = async () => {
    setClearing(true);
    try {
      const result = await apiService.clearDatabase({
        confirm: true,
        ...clearOptions,
      });
      setClearResult(result);
      setClearDialogOpen(false);
      showSuccess(result.message);
      await fetchDbStats();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao limpar banco de dados');
    } finally {
      setClearing(false);
    }
  };

  const handleResetSequences = async () => {
    try {
      const result = await apiService.resetDatabaseSequences();
      showSuccess(`${result.sequences_reset.length} sequences resetadas`);
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao resetar sequences');
    }
  };

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Configuracoes do Sistema
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Todas as configuracoes do sistema podem ser ajustadas aqui
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          {hasChanges && (
            <Button
              variant="contained"
              color="primary"
              startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
              onClick={handleSave}
              disabled={saving}
            >
              Salvar Alteracoes
            </Button>
          )}
          {config?.has_overrides && (
            <Tooltip title="Restaurar todos os valores padrao">
              <Button
                variant="outlined"
                color="warning"
                startIcon={<RestartAlt />}
                onClick={() => setResetDialogOpen(true)}
              >
                Resetar
              </Button>
            </Tooltip>
          )}
          <Tooltip title="Atualizar">
            <IconButton onClick={() => { fetchConfig(); fetchHealth(); }}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Override indicator */}
      {config?.has_overrides && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {config.override_keys.length} configuracao(oes) personalizada(s) ativa(s).
          Estas sobrescrevem os valores do arquivo .env.
        </Alert>
      )}

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        {categories.map((cat) => (
          <Tab
            key={cat.category}
            label={cat.label}
            icon={iconMap[cat.icon] || <SettingsIcon />}
            iconPosition="start"
            sx={{ minHeight: 48 }}
          />
        ))}
        <Tab
          label="Saude do Sistema"
          icon={<Memory />}
          iconPosition="start"
          sx={{ minHeight: 48 }}
        />
        <Tab
          label="Banco de Dados"
          icon={<Storage />}
          iconPosition="start"
          sx={{ minHeight: 48 }}
          onClick={() => { if (!dbStats) fetchDbStats(); }}
        />
      </Tabs>

      {/* Category Tabs */}
      {categories.map((cat, catIndex) => (
        tab === catIndex && (
          <Paper key={cat.category} sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
            <Box mb={3}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                {cat.label}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {cat.description}
              </Typography>
            </Box>

            <Grid container spacing={3}>
              {cat.fields.map((field) => (
                <Grid item xs={12} md={field.type === 'boolean' ? 6 : 6} key={field.key}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: config?.override_keys.includes(field.key)
                        ? 'primary.main'
                        : 'divider',
                      bgcolor: config?.override_keys.includes(field.key)
                        ? 'action.selected'
                        : 'transparent',
                      position: 'relative',
                    }}
                  >
                    {field.restart_required && (
                      <Tooltip title="Requer reiniciar os servicos">
                        <Chip
                          label="restart"
                          size="small"
                          color="warning"
                          variant="outlined"
                          sx={{
                            position: 'absolute',
                            top: 8,
                            right: 8,
                            fontSize: '0.65rem',
                            height: 20,
                          }}
                        />
                      </Tooltip>
                    )}
                    <ConfigFieldRenderer
                      field={field}
                      value={editedValues[field.key]}
                      onChange={handleFieldChange}
                    />
                  </Box>
                </Grid>
              ))}
            </Grid>

            {/* Save button at bottom of each category */}
            {hasChanges && (
              <Box mt={3} display="flex" justifyContent="flex-end">
                <Button
                  variant="contained"
                  startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
                  onClick={handleSave}
                  disabled={saving}
                >
                  Salvar Alteracoes
                </Button>
              </Box>
            )}
          </Paper>
        )
      ))}

      {/* Health Tab */}
      {tab === healthTabIndex && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Status dos Servicos
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box display="flex" alignItems="center" gap={1}>
                      <Storage fontSize="small" color="primary" />
                      <Typography variant="body2">Banco de Dados</Typography>
                    </Box>
                    <StatusChip status={health?.database} />
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box display="flex" alignItems="center" gap={1}>
                      <Memory fontSize="small" color="primary" />
                      <Typography variant="body2">Redis</Typography>
                    </Box>
                    <StatusChip status={health?.redis} />
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box display="flex" alignItems="center" gap={1}>
                      <SettingsIcon fontSize="small" color="primary" />
                      <Typography variant="body2">Celery</Typography>
                    </Box>
                    <StatusChip status={health?.celery} />
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box display="flex" alignItems="center" gap={1}>
                      <Security fontSize="small" color="primary" />
                      <Typography variant="body2">Vector DB</Typography>
                    </Box>
                    <StatusChip status={health?.vector_db} />
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Informacoes do Sistema
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Box display="flex" justifyContent="space-between" py={1}>
                    <Typography variant="body2" color="text.secondary">Versao</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {health?.version || '-'}
                    </Typography>
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" py={1}>
                    <Typography variant="body2" color="text.secondary">Status Geral</Typography>
                    <StatusChip status={health?.status} />
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" py={1}>
                    <Typography variant="body2" color="text.secondary">Categorias</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {categories.length}
                    </Typography>
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" py={1}>
                    <Typography variant="body2" color="text.secondary">Overrides Ativos</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {config?.override_keys.length || 0}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Database Management Tab */}
      {tab === databaseTabIndex && (
        <Box>
          <Grid container spacing={3}>
            {/* Stats Card */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6" fontWeight={600}>
                      Estatisticas do Banco
                    </Typography>
                    <IconButton onClick={fetchDbStats} disabled={dbLoading}>
                      <Refresh />
                    </IconButton>
                  </Box>
                  {dbLoading ? (
                    <Box display="flex" justifyContent="center" py={4}>
                      <CircularProgress />
                    </Box>
                  ) : dbStats ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                      {[
                        { label: 'Candidatos', value: dbStats.candidates, color: 'primary.main' },
                        { label: 'Documentos', value: dbStats.documents, color: 'info.main' },
                        { label: 'Chunks', value: dbStats.chunks, color: 'secondary.main' },
                        { label: 'Embeddings', value: dbStats.embeddings, color: 'success.main' },
                        { label: 'Experiencias', value: dbStats.experiences, color: 'warning.main' },
                        { label: 'Perfis', value: dbStats.profiles, color: 'error.main' },
                        { label: 'Conversas', value: dbStats.conversations, color: 'info.dark' },
                        { label: 'Mensagens', value: dbStats.messages, color: 'secondary.dark' },
                        { label: 'Logs de Auditoria', value: dbStats.audit_logs, color: 'text.secondary' },
                        { label: 'Logs de IA', value: dbStats.ai_usage_logs, color: 'text.secondary' },
                      ].map((item) => (
                        <Box key={item.label} display="flex" justifyContent="space-between" alignItems="center">
                          <Typography variant="body2">{item.label}</Typography>
                          <Chip
                            label={item.value.toLocaleString()}
                            size="small"
                            sx={{ fontWeight: 700 }}
                          />
                        </Box>
                      ))}
                      <Divider sx={{ my: 1 }} />
                      <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Typography variant="body2" fontWeight={700}>Total</Typography>
                        <Chip
                          label={dbStats.total_records.toLocaleString()}
                          size="small"
                          color="primary"
                          sx={{ fontWeight: 700 }}
                        />
                      </Box>
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Clique em atualizar para carregar estatisticas
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* Actions Card */}
            <Grid item xs={12} md={6}>
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Gerenciamento de Dados
                  </Typography>

                  <Alert severity="warning" sx={{ mb: 2 }}>
                    As operacoes abaixo sao <strong>IRREVERSIVEIS</strong>.
                    Certifique-se de ter backup antes de prosseguir.
                  </Alert>

                  <Box display="flex" flexDirection="column" gap={2}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                        Opcoes de Limpeza
                      </Typography>

                      <FormControlLabel
                        control={
                          <Switch
                            checked={clearOptions.clear_candidates}
                            onChange={(e) =>
                              setClearOptions((prev) => ({
                                ...prev,
                                clear_candidates: e.target.checked,
                                clear_documents: e.target.checked || prev.clear_documents,
                              }))
                            }
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">Candidatos e Curriculos</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Apaga candidatos, documentos, chunks, embeddings, experiencias, perfis
                            </Typography>
                          </Box>
                        }
                        sx={{ ml: 0, width: '100%', mb: 1 }}
                      />

                      <FormControlLabel
                        control={
                          <Switch
                            checked={clearOptions.clear_conversations}
                            onChange={(e) =>
                              setClearOptions((prev) => ({
                                ...prev,
                                clear_conversations: e.target.checked,
                              }))
                            }
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">Conversas do Chat</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Apaga todas as conversas e mensagens
                            </Typography>
                          </Box>
                        }
                        sx={{ ml: 0, width: '100%', mb: 1 }}
                      />

                      <FormControlLabel
                        control={
                          <Switch
                            checked={clearOptions.clear_audit_logs}
                            onChange={(e) =>
                              setClearOptions((prev) => ({
                                ...prev,
                                clear_audit_logs: e.target.checked,
                              }))
                            }
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">Logs de Auditoria</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Apaga historico de acoes
                            </Typography>
                          </Box>
                        }
                        sx={{ ml: 0, width: '100%', mb: 1 }}
                      />

                      <FormControlLabel
                        control={
                          <Switch
                            checked={clearOptions.clear_ai_usage}
                            onChange={(e) =>
                              setClearOptions((prev) => ({
                                ...prev,
                                clear_ai_usage: e.target.checked,
                              }))
                            }
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">Logs de Uso de IA</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Apaga registros de consumo de tokens e custos
                            </Typography>
                          </Box>
                        }
                        sx={{ ml: 0, width: '100%', mb: 1 }}
                      />

                      <FormControlLabel
                        control={
                          <Switch
                            checked={clearOptions.reset_sequences}
                            onChange={(e) =>
                              setClearOptions((prev) => ({
                                ...prev,
                                reset_sequences: e.target.checked,
                              }))
                            }
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">Resetar Contadores (IDs)</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Recomecar contagem de IDs do 1 nas tabelas limpas
                            </Typography>
                          </Box>
                        }
                        sx={{ ml: 0, width: '100%', mb: 2 }}
                      />
                    </Box>

                    <Divider />

                    <Box display="flex" gap={2} flexWrap="wrap">
                      <Button
                        variant="contained"
                        color="error"
                        startIcon={<DeleteForever />}
                        onClick={() => setClearDialogOpen(true)}
                        disabled={
                          !clearOptions.clear_candidates &&
                          !clearOptions.clear_conversations &&
                          !clearOptions.clear_audit_logs &&
                          !clearOptions.clear_ai_usage
                        }
                      >
                        Limpar Dados Selecionados
                      </Button>

                      <Button
                        variant="outlined"
                        startIcon={<CleaningServices />}
                        onClick={handleResetSequences}
                      >
                        Resetar Sequences
                      </Button>
                    </Box>
                  </Box>
                </CardContent>
              </Card>

              {/* Clear Result */}
              {clearResult && (
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                      Ultimo resultado da limpeza
                    </Typography>
                    <Alert severity="success" sx={{ mb: 2 }}>
                      {clearResult.message}
                    </Alert>
                    <Box display="flex" gap={1} flexWrap="wrap">
                      {Object.entries(clearResult.deleted || {}).map(([key, value]) => (
                        <Chip
                          key={key}
                          label={`${key}: ${value}`}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                    {clearResult.sequences_reset?.length > 0 && (
                      <Box mt={1}>
                        <Typography variant="caption" color="text.secondary">
                          Sequences resetadas: {clearResult.sequences_reset.join(', ')}
                        </Typography>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              )}
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Clear Database Confirmation Dialog */}
      <Dialog open={clearDialogOpen} onClose={() => setClearDialogOpen(false)}>
        <DialogTitle fontWeight={600} color="error.main">
          Confirmar Limpeza do Banco de Dados
        </DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            Esta operacao e <strong>IRREVERSIVEL</strong>! Todos os dados selecionados serao
            permanentemente apagados.
          </Alert>
          <Typography variant="body2" gutterBottom>
            Serao apagados:
          </Typography>
          <Box sx={{ ml: 2, mb: 2 }}>
            {clearOptions.clear_candidates && (
              <Typography variant="body2">- Todos os candidatos, documentos, chunks, embeddings</Typography>
            )}
            {clearOptions.clear_conversations && (
              <Typography variant="body2">- Todas as conversas do chat</Typography>
            )}
            {clearOptions.clear_audit_logs && (
              <Typography variant="body2">- Todos os logs de auditoria</Typography>
            )}
            {clearOptions.clear_ai_usage && (
              <Typography variant="body2">- Todos os logs de uso de IA</Typography>
            )}
            {clearOptions.reset_sequences && (
              <Typography variant="body2">- Contadores de ID serao resetados para 1</Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setClearDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleClearDatabase}
            disabled={clearing}
            startIcon={clearing ? <CircularProgress size={18} color="inherit" /> : <DeleteForever />}
          >
            {clearing ? 'Limpando...' : 'Confirmar Limpeza'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Restart Warning Dialog */}
      <Dialog
        open={restartWarningOpen}
        onClose={() => setRestartWarningOpen(false)}
      >
        <DialogTitle fontWeight={600}>
          Reinicio Necessario
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Algumas configuracoes alteradas requerem reiniciar os servicos Docker para entrarem em vigor.
          </Alert>
          <Typography variant="body2">
            Apos salvar, execute no servidor:
          </Typography>
          <Box
            sx={{
              mt: 1,
              p: 1.5,
              bgcolor: 'grey.100',
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.85rem',
            }}
          >
            docker compose -f docker-compose.prod.yml restart api celery-worker
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setRestartWarningOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => pendingSave && doSave(pendingSave)}
            disabled={saving}
            startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
          >
            Salvar Mesmo Assim
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reset Confirmation Dialog */}
      <Dialog open={resetDialogOpen} onClose={() => setResetDialogOpen(false)}>
        <DialogTitle fontWeight={600}>
          Restaurar Configuracoes Padrao
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Isso vai remover TODAS as personalizacoes feitas pelo frontend,
            voltando aos valores definidos no arquivo .env e nos padroes do sistema.
          </Alert>
          <Typography variant="body2">
            Esta acao requer reiniciar os servicos para ter efeito completo.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setResetDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={handleReset}
            startIcon={<RestartAlt />}
          >
            Restaurar Padroes
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SettingsPage;
