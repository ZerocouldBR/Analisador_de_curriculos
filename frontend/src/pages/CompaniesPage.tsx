import React, { useEffect, useState, useRef } from 'react';
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
  Avatar,
  CircularProgress,
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Business,
  Refresh,
  CheckCircle,
  Cancel,
  People,
  Description,
  Email,
  Phone,
  LocationOn,
  Language,
  CloudUpload,
  DeleteOutline,
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

const brStates = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO',
  'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI',
  'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
];

interface CompanyFormData {
  name: string;
  cnpj: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  website: string;
  plan: string;
}

const emptyForm: CompanyFormData = {
  name: '',
  cnpj: '',
  email: '',
  phone: '',
  address: '',
  city: '',
  state: '',
  website: '',
  plan: 'free',
};

const CompaniesPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [formData, setFormData] = useState<CompanyFormData>({ ...emptyForm });
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

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
        email: company.email || '',
        phone: company.phone || '',
        address: company.address || '',
        city: company.city || '',
        state: company.state || '',
        website: company.website || '',
        plan: company.plan,
      });
    } else {
      setEditingCompany(null);
      setFormData({ ...emptyForm });
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
    if (window.confirm(`Tem certeza que deseja desativar "${name}"? Os dados serao preservados.`)) {
      try {
        await apiService.deleteCompany(id);
        showSuccess('Empresa desativada com sucesso');
        fetchCompanies();
      } catch (error) {
        showError('Erro ao desativar empresa');
      }
    }
  };

  const updateField = (field: keyof CompanyFormData, value: string) => {
    setFormData({ ...formData, [field]: value });
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !editingCompany) return;

    setUploadingLogo(true);
    try {
      await apiService.uploadCompanyLogo(editingCompany.id, file);
      showSuccess('Logo atualizado com sucesso');
      fetchCompanies();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao enviar logo');
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = '';
    }
  };

  const handleLogoDelete = async () => {
    if (!editingCompany) return;
    try {
      await apiService.deleteCompanyLogo(editingCompany.id);
      showSuccess('Logo removido');
      fetchCompanies();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao remover logo');
    }
  };

  if (loading) return <TableSkeleton />;

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Empresas de RH
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Gerencie as empresas de RH, seus dados e planos de uso
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
                      {company.logo_url ? (
                        <Avatar
                          src={apiService.getCompanyLogoUrl(company.id)}
                          variant="rounded"
                          sx={{ width: 44, height: 44 }}
                        >
                          <Business />
                        </Avatar>
                      ) : (
                        <Box
                          sx={{
                            p: 1.5,
                            borderRadius: 2,
                            bgcolor: alpha(theme.palette.primary.main, 0.1),
                          }}
                        >
                          <Business color="primary" />
                        </Box>
                      )}
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

                  {/* Contadores */}
                  {(company.user_count !== undefined || company.candidate_count !== undefined) && (
                    <>
                      {company.user_count !== undefined && (
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <People sx={{ fontSize: 16, color: 'text.secondary' }} />
                            <Typography variant="body2" color="text.secondary">Usuarios</Typography>
                          </Box>
                          <Typography variant="body2" fontWeight={600}>{company.user_count}</Typography>
                        </Box>
                      )}
                      {company.candidate_count !== undefined && (
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <Description sx={{ fontSize: 16, color: 'text.secondary' }} />
                            <Typography variant="body2" color="text.secondary">Candidatos</Typography>
                          </Box>
                          <Typography variant="body2" fontWeight={600}>{company.candidate_count}</Typography>
                        </Box>
                      )}
                    </>
                  )}

                  {/* Contato */}
                  {company.email && (
                    <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                      <Email sx={{ fontSize: 14, color: 'text.disabled' }} />
                      <Typography variant="caption" color="text.secondary">{company.email}</Typography>
                    </Box>
                  )}
                  {company.phone && (
                    <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                      <Phone sx={{ fontSize: 14, color: 'text.disabled' }} />
                      <Typography variant="caption" color="text.secondary">{company.phone}</Typography>
                    </Box>
                  )}
                  {(company.city || company.state) && (
                    <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                      <LocationOn sx={{ fontSize: 14, color: 'text.disabled' }} />
                      <Typography variant="caption" color="text.secondary">
                        {[company.city, company.state].filter(Boolean).join(' - ')}
                      </Typography>
                    </Box>
                  )}
                  {company.website && (
                    <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                      <Language sx={{ fontSize: 14, color: 'text.disabled' }} />
                      <Typography variant="caption" color="text.secondary">{company.website}</Typography>
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
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Cadastre empresas de RH para gerenciar candidatos e curriculos de forma isolada.
          </Typography>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
            Cadastrar primeira empresa
          </Button>
        </Paper>
      )}

      {/* Dialog de cadastro/edicao */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle fontWeight={600}>
          {editingCompany ? 'Editar Empresa de RH' : 'Nova Empresa de RH'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Logo */}
            {editingCompany && (
              <>
                <Typography variant="subtitle2" color="primary" fontWeight={600}>
                  Logo da Empresa
                </Typography>
                <Box display="flex" alignItems="center" gap={2}>
                  {editingCompany.logo_url ? (
                    <Avatar
                      src={apiService.getCompanyLogoUrl(editingCompany.id)}
                      variant="rounded"
                      sx={{ width: 64, height: 64 }}
                    >
                      <Business />
                    </Avatar>
                  ) : (
                    <Avatar
                      variant="rounded"
                      sx={{
                        width: 64,
                        height: 64,
                        bgcolor: alpha(theme.palette.primary.main, 0.1),
                      }}
                    >
                      <Business color="primary" />
                    </Avatar>
                  )}
                  <Box>
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept=".png,.jpg,.jpeg,.svg,.webp"
                      style={{ display: 'none' }}
                      onChange={handleLogoUpload}
                    />
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={uploadingLogo ? <CircularProgress size={16} /> : <CloudUpload />}
                      onClick={() => logoInputRef.current?.click()}
                      disabled={uploadingLogo}
                      sx={{ mr: 1 }}
                    >
                      {uploadingLogo ? 'Enviando...' : 'Enviar Logo'}
                    </Button>
                    {editingCompany.logo_url && (
                      <Button
                        size="small"
                        color="error"
                        startIcon={<DeleteOutline />}
                        onClick={handleLogoDelete}
                      >
                        Remover
                      </Button>
                    )}
                    <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                      PNG, JPG, SVG ou WEBP (max 500KB)
                    </Typography>
                  </Box>
                </Box>
              </>
            )}

            {/* Dados basicos */}
            <Typography variant="subtitle2" color="primary" fontWeight={600}>
              Dados da Empresa
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={8}>
                <TextField
                  label="Nome da Empresa *"
                  fullWidth
                  value={formData.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  required
                  autoFocus
                  placeholder="Ex: RH Solutions Ltda"
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField
                  label="CNPJ"
                  fullWidth
                  value={formData.cnpj}
                  onChange={(e) => updateField('cnpj', e.target.value)}
                  placeholder="00.000.000/0001-00"
                />
              </Grid>
            </Grid>

            {/* Contato */}
            <Typography variant="subtitle2" color="primary" fontWeight={600} sx={{ mt: 1 }}>
              Contato
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Email"
                  fullWidth
                  type="email"
                  value={formData.email}
                  onChange={(e) => updateField('email', e.target.value)}
                  placeholder="contato@empresa.com.br"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Telefone"
                  fullWidth
                  value={formData.phone}
                  onChange={(e) => updateField('phone', e.target.value)}
                  placeholder="(00) 00000-0000"
                />
              </Grid>
            </Grid>

            {/* Endereco */}
            <Typography variant="subtitle2" color="primary" fontWeight={600} sx={{ mt: 1 }}>
              Endereco
            </Typography>
            <TextField
              label="Endereco"
              fullWidth
              value={formData.address}
              onChange={(e) => updateField('address', e.target.value)}
              placeholder="Rua, numero, complemento"
            />
            <Grid container spacing={2}>
              <Grid item xs={12} sm={8}>
                <TextField
                  label="Cidade"
                  fullWidth
                  value={formData.city}
                  onChange={(e) => updateField('city', e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField
                  label="Estado"
                  select
                  fullWidth
                  value={formData.state}
                  onChange={(e) => updateField('state', e.target.value)}
                >
                  <MenuItem value="">Selecione</MenuItem>
                  {brStates.map((s) => (
                    <MenuItem key={s} value={s}>{s}</MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>

            {/* Web e plano */}
            <Typography variant="subtitle2" color="primary" fontWeight={600} sx={{ mt: 1 }}>
              Web e Plano
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={8}>
                <TextField
                  label="Website"
                  fullWidth
                  value={formData.website}
                  onChange={(e) => updateField('website', e.target.value)}
                  placeholder="https://www.empresa.com.br"
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField
                  label="Plano"
                  select
                  fullWidth
                  value={formData.plan}
                  onChange={(e) => updateField('plan', e.target.value)}
                >
                  {plans.map((plan) => (
                    <MenuItem key={plan.value} value={plan.value}>
                      {plan.label}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOpenDialog(false)}>Cancelar</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingCompany ? 'Salvar Alteracoes' : 'Cadastrar Empresa'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CompaniesPage;
