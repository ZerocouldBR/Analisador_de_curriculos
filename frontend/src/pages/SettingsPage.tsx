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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Snackbar,
  Alert,
  Divider,
} from '@mui/material';
import { Edit, Save } from '@mui/icons-material';
import { apiService } from '../services/api';
import { ServerSettings } from '../types';

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<ServerSettings[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingSetting, setEditingSetting] = useState<ServerSettings | null>(null);
  const [editValue, setEditValue] = useState('');
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success' as 'success' | 'error',
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const data = await apiService.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Error fetching settings:', error);
      showSnackbar('Erro ao carregar configurações', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleEdit = (setting: ServerSettings) => {
    setEditingSetting(setting);
    setEditValue(JSON.stringify(setting.value_json, null, 2));
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!editingSetting) return;

    try {
      const value = JSON.parse(editValue);
      await apiService.updateSetting(editingSetting.key, value);
      showSnackbar('Configuração atualizada com sucesso', 'success');
      setOpenDialog(false);
      fetchSettings();
    } catch (error) {
      console.error('Error saving setting:', error);
      showSnackbar('Erro ao salvar configuração', 'error');
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Configurações do Sistema
      </Typography>

      <Paper sx={{ mt: 3 }}>
        <List>
          {settings.map((setting, index) => (
            <React.Fragment key={setting.id}>
              {index > 0 && <Divider />}
              <ListItem>
                <ListItemText
                  primary={setting.key}
                  secondary={
                    <>
                      {setting.description && (
                        <Typography variant="body2" color="text.secondary">
                          {setting.description}
                        </Typography>
                      )}
                      <Typography variant="caption" color="text.secondary">
                        Versão: {setting.version} | Atualizado em:{' '}
                        {new Date(setting.updated_at).toLocaleString()}
                      </Typography>
                    </>
                  }
                />
                <Button
                  startIcon={<Edit />}
                  onClick={() => handleEdit(setting)}
                  variant="outlined"
                  size="small"
                >
                  Editar
                </Button>
              </ListItem>
            </React.Fragment>
          ))}
        </List>
      </Paper>

      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          Editar Configuração: {editingSetting?.key}
        </DialogTitle>
        <DialogContent>
          {editingSetting?.description && (
            <Alert severity="info" sx={{ mb: 2 }}>
              {editingSetting.description}
            </Alert>
          )}
          <TextField
            fullWidth
            multiline
            rows={15}
            label="Valor (JSON)"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            sx={{ fontFamily: 'monospace' }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancelar</Button>
          <Button onClick={handleSave} variant="contained" startIcon={<Save />}>
            Salvar
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default SettingsPage;
