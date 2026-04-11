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
  // Last tab index is health
  const healthTabIndex = categories.length;

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
