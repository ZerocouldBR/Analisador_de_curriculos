import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Grid,
  Divider,
  Switch,
  FormControlLabel,
  IconButton,
  Tooltip,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Add,
  Edit,
  AdminPanelSettings,
  Security,
  Refresh,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Role } from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { TableSkeleton } from '../components/LoadingSkeleton';

const permissionGroups: Record<string, string[]> = {
  Candidatos: ['candidates.read', 'candidates.create', 'candidates.update', 'candidates.delete'],
  Documentos: ['documents.read', 'documents.create', 'documents.update', 'documents.delete'],
  Busca: ['search.execute'],
  Configuracoes: ['settings.read', 'settings.update'],
  Funcoes: ['roles.read', 'roles.create', 'roles.update', 'roles.delete'],
};

const permissionLabels: Record<string, string> = {
  'candidates.read': 'Visualizar',
  'candidates.create': 'Criar',
  'candidates.update': 'Editar',
  'candidates.delete': 'Excluir',
  'documents.read': 'Visualizar',
  'documents.create': 'Upload',
  'documents.update': 'Editar',
  'documents.delete': 'Excluir',
  'search.execute': 'Executar buscas',
  'settings.read': 'Visualizar',
  'settings.update': 'Alterar',
  'roles.read': 'Visualizar',
  'roles.create': 'Criar',
  'roles.update': 'Editar',
  'roles.delete': 'Excluir',
};

const RolesPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    permissions: {} as Record<string, boolean>,
  });

  const allPermissions = Object.values(permissionGroups).flat();

  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const data = await apiService.getRoles();
      setRoles(data);
    } catch (error) {
      showError('Erro ao carregar funcoes');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (role?: Role) => {
    if (role) {
      setEditingRole(role);
      setFormData({
        name: role.name,
        description: role.description || '',
        permissions: { ...role.permissions },
      });
    } else {
      setEditingRole(null);
      const defaultPermissions: Record<string, boolean> = {};
      allPermissions.forEach((perm) => { defaultPermissions[perm] = false; });
      setFormData({ name: '', description: '', permissions: defaultPermissions });
    }
    setOpenDialog(true);
  };

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      showError('Nome da funcao e obrigatorio');
      return;
    }
    try {
      if (editingRole) {
        await apiService.updateRole(editingRole.id, formData);
        showSuccess('Funcao atualizada com sucesso');
      } else {
        await apiService.createRole(formData);
        showSuccess('Funcao criada com sucesso');
      }
      setOpenDialog(false);
      setEditingRole(null);
      fetchRoles();
    } catch (error) {
      showError('Erro ao salvar funcao');
    }
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

  const handleGroupToggle = (group: string) => {
    const perms = permissionGroups[group];
    const allEnabled = perms.every((p) => formData.permissions[p]);
    const newPermissions = { ...formData.permissions };
    perms.forEach((p) => { newPermissions[p] = !allEnabled; });
    setFormData({ ...formData, permissions: newPermissions });
  };

  const getEnabledCount = (role: Role) =>
    Object.values(role.permissions).filter(Boolean).length;

  if (loading) return <TableSkeleton />;

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Funcoes e Permissoes
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Gerencie as funcoes de usuario e suas permissoes de acesso
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title="Atualizar">
            <IconButton onClick={fetchRoles}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
            Nova Funcao
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {roles.map((role) => (
          <Grid item xs={12} md={6} key={role.id}>
            <Paper
              sx={{
                p: 3,
                border: '1px solid',
                borderColor: 'divider',
                transition: 'box-shadow 0.2s',
                '&:hover': { boxShadow: theme.shadows[3] },
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
                <Box display="flex" alignItems="center" gap={1.5}>
                  <Box
                    sx={{
                      p: 1,
                      borderRadius: 2,
                      bgcolor: alpha(theme.palette.primary.main, 0.1),
                    }}
                  >
                    <Security color="primary" />
                  </Box>
                  <Box>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {role.name}
                    </Typography>
                    {role.description && (
                      <Typography variant="caption" color="text.secondary">
                        {role.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
                <Button
                  startIcon={<Edit />}
                  onClick={() => handleOpenDialog(role)}
                  size="small"
                  variant="outlined"
                >
                  Editar
                </Button>
              </Box>

              <Divider sx={{ mb: 2 }} />

              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                <Typography variant="caption" color="text.secondary" fontWeight={500}>
                  PERMISSOES ATIVAS
                </Typography>
                <Chip
                  label={`${getEnabledCount(role)}/${allPermissions.length}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              </Box>

              <Box display="flex" flexWrap="wrap" gap={0.5}>
                {Object.entries(role.permissions)
                  .filter(([_, enabled]) => enabled)
                  .map(([permission]) => (
                    <Chip
                      key={permission}
                      label={permission}
                      size="small"
                      sx={{ fontSize: '0.7rem' }}
                    />
                  ))}
                {getEnabledCount(role) === 0 && (
                  <Typography variant="caption" color="text.disabled">
                    Nenhuma permissao ativa
                  </Typography>
                )}
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {roles.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
          <AdminPanelSettings sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Nenhuma funcao cadastrada
          </Typography>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
            Criar primeira funcao
          </Button>
        </Paper>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle fontWeight={600}>
          {editingRole ? 'Editar Funcao' : 'Nova Funcao'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Nome da Funcao"
              fullWidth
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              autoFocus
            />
            <TextField
              label="Descricao"
              fullWidth
              multiline
              rows={2}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />

            <Typography variant="h6" fontWeight={600} sx={{ mt: 1 }}>
              Permissoes
            </Typography>

            {Object.entries(permissionGroups).map(([group, perms]) => {
              const allEnabled = perms.every((p) => formData.permissions[p]);
              const someEnabled = perms.some((p) => formData.permissions[p]);

              return (
                <Paper key={group} sx={{ p: 2, border: '1px solid', borderColor: 'divider' }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="subtitle2" fontWeight={600}>
                      {group}
                    </Typography>
                    <Button
                      size="small"
                      onClick={() => handleGroupToggle(group)}
                      variant={allEnabled ? 'contained' : 'outlined'}
                    >
                      {allEnabled ? 'Desmarcar todos' : 'Marcar todos'}
                    </Button>
                  </Box>
                  <Box display="flex" flexWrap="wrap" gap={1}>
                    {perms.map((perm) => (
                      <Chip
                        key={perm}
                        label={permissionLabels[perm] || perm}
                        onClick={() => handlePermissionToggle(perm)}
                        color={formData.permissions[perm] ? 'primary' : 'default'}
                        variant={formData.permissions[perm] ? 'filled' : 'outlined'}
                        sx={{ cursor: 'pointer' }}
                      />
                    ))}
                  </Box>
                </Paper>
              );
            })}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOpenDialog(false)}>Cancelar</Button>
          <Button onClick={handleSubmit} variant="contained">
            Salvar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RolesPage;
