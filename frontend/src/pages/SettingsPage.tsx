import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
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
  useTheme,
  alpha,
} from '@mui/material';
import {
  Edit,
  Save,
  Settings as SettingsIcon,
  Memory,
  Storage,
  Security,
  Refresh,
  CheckCircle,
  Warning,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { ServerSettings, HealthCheck } from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { TableSkeleton } from '../components/LoadingSkeleton';

const SettingsPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [settings, setSettings] = useState<ServerSettings[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingSetting, setEditingSetting] = useState<ServerSettings | null>(null);
  const [editValue, setEditValue] = useState('');
  const [tab, setTab] = useState(0);
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [jsonError, setJsonError] = useState('');

  useEffect(() => {
    fetchSettings();
    fetchHealth();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const data = await apiService.getSettings();
      setSettings(data);
    } catch (error) {
      showError('Erro ao carregar configuracoes');
    } finally {
      setLoading(false);
    }
  };

  const fetchHealth = async () => {
    try {
      const data = await apiService.healthCheck();
      setHealth(data);
    } catch (error) {
      console.error('Health check failed:', error);
    }
  };

  const handleEdit = (setting: ServerSettings) => {
    setEditingSetting(setting);
    setEditValue(JSON.stringify(setting.value_json, null, 2));
    setJsonError('');
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!editingSetting) return;
    try {
      const value = JSON.parse(editValue);
      setJsonError('');
      await apiService.updateSetting(editingSetting.key, value);
      showSuccess('Configuracao atualizada com sucesso');
      setOpenDialog(false);
      fetchSettings();
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        setJsonError('JSON invalido. Verifique a sintaxe.');
      } else {
        showError('Erro ao salvar configuracao');
      }
    }
  };

  const handleEditValueChange = (value: string) => {
    setEditValue(value);
    try {
      JSON.parse(value);
      setJsonError('');
    } catch {
      setJsonError('JSON invalido');
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

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Configuracoes do Sistema
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Gerencie as configuracoes do servidor e monitore a saude do sistema
          </Typography>
        </Box>
        <Tooltip title="Atualizar">
          <IconButton onClick={() => { fetchSettings(); fetchHealth(); }}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Configuracoes" icon={<SettingsIcon />} iconPosition="start" />
        <Tab label="Saude do Sistema" icon={<Memory />} iconPosition="start" />
      </Tabs>

      {/* Settings Tab */}
      {tab === 0 && (
        <Paper sx={{ border: '1px solid', borderColor: 'divider' }}>
          <List disablePadding>
            {settings.map((setting, index) => (
              <React.Fragment key={setting.id}>
                {index > 0 && <Divider />}
                <ListItem
                  sx={{
                    py: 2,
                    px: 3,
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                  secondaryAction={
                    <Button
                      startIcon={<Edit />}
                      onClick={() => handleEdit(setting)}
                      variant="outlined"
                      size="small"
                    >
                      Editar
                    </Button>
                  }
                >
                  <ListItemIcon>
                    <SettingsIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="body1" fontWeight={600}>
                        {setting.key}
                      </Typography>
                    }
                    secondary={
                      <Box>
                        {setting.description && (
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {setting.description}
                          </Typography>
                        )}
                        <Box display="flex" gap={1} mt={1}>
                          <Chip label={`v${setting.version}`} size="small" variant="outlined" />
                          <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                            Atualizado em {new Date(setting.updated_at).toLocaleString('pt-BR')}
                          </Typography>
                        </Box>
                      </Box>
                    }
                  />
                </ListItem>
              </React.Fragment>
            ))}
            {settings.length === 0 && (
              <ListItem sx={{ py: 4 }}>
                <ListItemText
                  primary={
                    <Typography textAlign="center" color="text.secondary">
                      Nenhuma configuracao encontrada
                    </Typography>
                  }
                />
              </ListItem>
            )}
          </List>
        </Paper>
      )}

      {/* Health Tab */}
      {tab === 1 && (
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
                      {health?.version || '0.3.0'}
                    </Typography>
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" py={1}>
                    <Typography variant="body2" color="text.secondary">Status Geral</Typography>
                    <StatusChip status={health?.status} />
                  </Box>
                  <Divider />
                  <Box display="flex" justifyContent="space-between" py={1}>
                    <Typography variant="body2" color="text.secondary">Configuracoes</Typography>
                    <Typography variant="body2" fontWeight={600}>{settings.length}</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Edit Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle fontWeight={600}>
          Editar: {editingSetting?.key}
        </DialogTitle>
        <DialogContent>
          {editingSetting?.description && (
            <Alert severity="info" sx={{ mb: 2 }}>
              {editingSetting.description}
            </Alert>
          )}
          {jsonError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {jsonError}
            </Alert>
          )}
          <TextField
            fullWidth
            multiline
            rows={18}
            label="Valor (JSON)"
            value={editValue}
            onChange={(e) => handleEditValueChange(e.target.value)}
            error={!!jsonError}
            InputProps={{
              sx: { fontFamily: 'monospace', fontSize: '0.85rem' },
            }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOpenDialog(false)}>Cancelar</Button>
          <Button
            onClick={handleSave}
            variant="contained"
            startIcon={<Save />}
            disabled={!!jsonError}
          >
            Salvar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SettingsPage;
