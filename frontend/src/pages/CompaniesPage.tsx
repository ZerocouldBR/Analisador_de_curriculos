import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Divider,
  IconButton,
  Tooltip,
  MenuItem,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Business,
  Refresh,
  CheckCircle,
  Cancel,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Company } from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { TableSkeleton } from '../components/LoadingSkeleton';

const plans = [
  { value: 'free', label: 'Free', color: 'default' as const },
  { value: 'basic', label: 'Basic', color: 'info' as const },
  { value: 'pro', label: 'Pro', color: 'primary' as const },
  { value: 'enterprise', label: 'Enterprise', color: 'secondary' as const },
];

const CompaniesPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    cnpj: '',
    plan: 'free',
    max_candidates: 100,
    max_monthly_ai_cost: 50,
  });

  useEffect(() => {
    fetchCompanies();
  }, []);

  const fetchCompanies = async () => {
    try {
      setLoading(true);
      const data = await apiService.getCompanies();
      setCompanies(data);
    } catch (error) {
      showError('Erro ao carregar empresas');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (company?: Company) => {
    if (company) {
      setEditingCompany(company);
      setFormData({
        name: company.name,
        cnpj: company.cnpj || '',
        plan: company.plan,
        max_candidates: company.max_candidates || 100,
        max_monthly_ai_cost: company.max_monthly_ai_cost || 50,
      });
    } else {
      setEditingCompany(null);
      setFormData({ name: '', cnpj: '', plan: 'free', max_candidates: 100, max_monthly_ai_cost: 50 });
    }
    setOpenDialog(true);
  };

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      showError('Nome da empresa e obrigatorio');
      return;
    }
    try {
      if (editingCompany) {
        await apiService.updateCompany(editingCompany.id, formData);
        showSuccess('Empresa atualizada com sucesso');
      } else {
        await apiService.createCompany(formData);
        showSuccess('Empresa criada com sucesso');
      }
      setOpenDialog(false);
      setEditingCompany(null);
      fetchCompanies();
    } catch (error) {
      showError('Erro ao salvar empresa');
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (window.confirm(`Tem certeza que deseja excluir "${name}"?`)) {
      try {
        await apiService.deleteCompany(id);
        showSuccess('Empresa excluida com sucesso');
        fetchCompanies();
      } catch (error) {
        showError('Erro ao excluir empresa');
      }
    }
  };

  if (loading) return <TableSkeleton />;

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Empresas
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Gerencie as empresas e seus planos de uso
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title="Atualizar">
            <IconButton onClick={fetchCompanies}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
            Nova Empresa
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {companies.map((company) => {
          const planInfo = plans.find((p) => p.value === company.plan) || plans[0];
          return (
            <Grid item xs={12} sm={6} md={4} key={company.id}>
              <Card
                sx={{
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': { transform: 'translateY(-2px)', boxShadow: theme.shadows[4] },
                }}
              >
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="start">
                    <Box display="flex" alignItems="center" gap={1.5}>
                      <Box
                        sx={{
                          p: 1.5,
                          borderRadius: 2,
                          bgcolor: alpha(theme.palette.primary.main, 0.1),
                        }}
                      >
                        <Business color="primary" />
                      </Box>
                      <Box>
                        <Typography variant="subtitle1" fontWeight={600}>
                          {company.name}
                        </Typography>
                        {company.cnpj && (
                          <Typography variant="caption" color="text.secondary">
                            CNPJ: {company.cnpj}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                    <Box>
                      <IconButton size="small" onClick={() => handleOpenDialog(company)}>
                        <Edit fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(company.id, company.name)}
                        sx={{ color: 'error.main' }}
                      >
                        <Delete fontSize="small" />
                      </IconButton>
                    </Box>
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2" color="text.secondary">Plano</Typography>
                    <Chip label={planInfo.label} size="small" color={planInfo.color} />
                  </Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2" color="text.secondary">Status</Typography>
                    <Chip
                      icon={company.is_active ? <CheckCircle /> : <Cancel />}
                      label={company.is_active ? 'Ativa' : 'Inativa'}
                      size="small"
                      color={company.is_active ? 'success' : 'error'}
                      variant="outlined"
                    />
                  </Box>
                  {company.max_candidates && (
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="body2" color="text.secondary">Max. Candidatos</Typography>
                      <Typography variant="body2" fontWeight={600}>{company.max_candidates}</Typography>
                    </Box>
                  )}
                  <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                    Criada em {new Date(company.created_at).toLocaleDateString('pt-BR')}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {companies.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
          <Business sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Nenhuma empresa cadastrada
          </Typography>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
            Criar primeira empresa
          </Button>
        </Paper>
      )}

      {/* Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle fontWeight={600}>
          {editingCompany ? 'Editar Empresa' : 'Nova Empresa'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Nome da Empresa"
              fullWidth
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              autoFocus
            />
            <TextField
              label="CNPJ"
              fullWidth
              value={formData.cnpj}
              onChange={(e) => setFormData({ ...formData, cnpj: e.target.value })}
            />
            <TextField
              label="Plano"
              select
              fullWidth
              value={formData.plan}
              onChange={(e) => setFormData({ ...formData, plan: e.target.value })}
            >
              {plans.map((plan) => (
                <MenuItem key={plan.value} value={plan.value}>
                  {plan.label}
                </MenuItem>
              ))}
            </TextField>
            <Box display="flex" gap={2}>
              <TextField
                label="Max. Candidatos"
                type="number"
                fullWidth
                value={formData.max_candidates}
                onChange={(e) => setFormData({ ...formData, max_candidates: parseInt(e.target.value) || 0 })}
              />
              <TextField
                label="Max. Custo IA Mensal (USD)"
                type="number"
                fullWidth
                value={formData.max_monthly_ai_cost}
                onChange={(e) => setFormData({ ...formData, max_monthly_ai_cost: parseFloat(e.target.value) || 0 })}
              />
            </Box>
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

export default CompaniesPage;
