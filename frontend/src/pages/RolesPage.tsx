import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  List,
  ListItem,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Grid,
  CircularProgress,
  Snackbar,
  Alert,
  Divider,
} from '@mui/material';
import { Add, Edit } from '@mui/icons-material';
import { apiService } from '../services/api';
import { Role } from '../types';

const RolesPage: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    permissions: {} as Record<string, boolean>,
  });
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success' as 'success' | 'error',
  });

  const availablePermissions = [
    'candidates.read',
    'candidates.create',
    'candidates.update',
    'candidates.delete',
    'documents.read',
    'documents.create',
    'documents.update',
    'documents.delete',
    'search.execute',
    'settings.read',
    'settings.update',
    'roles.read',
    'roles.create',
    'roles.update',
    'roles.delete',
  ];

  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      const data = await apiService.getRoles();
      setRoles(data);
    } catch (error) {
      console.error('Error fetching roles:', error);
      showSnackbar('Erro ao carregar funções', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleOpenDialog = (role?: Role) => {
    if (role) {
      setEditingRole(role);
      setFormData({
        name: role.name,
        description: role.description || '',
        permissions: role.permissions,
      });
    } else {
      setEditingRole(null);
      const defaultPermissions: Record<string, boolean> = {};
      availablePermissions.forEach((perm) => {
        defaultPermissions[perm] = false;
      });
      setFormData({
        name: '',
        description: '',
        permissions: defaultPermissions,
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingRole(null);
  };

  const handlePermissionToggle = (permission: string) => {
    setFormData({
      ...formData,
      permissions: {
        ...formData.permissions,
        [permission]: !formData.permissions[permission],
      },
    });
  };

  const handleSubmit = async () => {
    try {
      if (editingRole) {
        await apiService.updateRole(editingRole.id, formData);
        showSnackbar('Função atualizada com sucesso', 'success');
      } else {
        await apiService.createRole(formData);
        showSnackbar('Função criada com sucesso', 'success');
      }
      handleCloseDialog();
      fetchRoles();
    } catch (error) {
      console.error('Error saving role:', error);
      showSnackbar('Erro ao salvar função', 'error');
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
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">Funções e Permissões</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
          Nova Função
        </Button>
      </Box>

      <Paper>
        <List>
          {roles.map((role, index) => (
            <React.Fragment key={role.id}>
              {index > 0 && <Divider />}
              <ListItem>
                <ListItemText
                  primary={role.name}
                  secondary={
                    <>
                      {role.description && (
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          {role.description}
                        </Typography>
                      )}
                      <Box mt={1}>
                        {Object.entries(role.permissions)
                          .filter(([_, enabled]) => enabled)
                          .map(([permission]) => (
                            <Chip
                              key={permission}
                              label={permission}
                              size="small"
                              sx={{ mr: 0.5, mb: 0.5 }}
                            />
                          ))}
                      </Box>
                    </>
                  }
                />
                <Button
                  startIcon={<Edit />}
                  onClick={() => handleOpenDialog(role)}
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

      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>{editingRole ? 'Editar Função' : 'Nova Função'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Nome"
            fullWidth
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <TextField
            margin="dense"
            label="Descrição"
            fullWidth
            multiline
            rows={2}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />

          <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
            Permissões
          </Typography>

          <Grid container spacing={1}>
            {availablePermissions.map((permission) => (
              <Grid item xs={12} sm={6} key={permission}>
                <Chip
                  label={permission}
                  onClick={() => handlePermissionToggle(permission)}
                  color={formData.permissions[permission] ? 'primary' : 'default'}
                  variant={formData.permissions[permission] ? 'filled' : 'outlined'}
                  sx={{ width: '100%', justifyContent: 'flex-start' }}
                />
              </Grid>
            ))}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancelar</Button>
          <Button onClick={handleSubmit} variant="contained">
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

export default RolesPage;
