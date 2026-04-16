import React, { useState, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Grid,
  Card,
  CardContent,
  Divider,
  Avatar,
  Chip,
  Alert,
  useTheme,
  alpha,
  InputAdornment,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  Person,
  Email,
  Lock,
  Visibility,
  VisibilityOff,
  Save,
  CalendarToday,
  Shield,
  Business,
  CloudUpload,
  Delete,
  Image,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNotification } from '../contexts/NotificationContext';
import { useCompany } from '../contexts/CompanyContext';
import { apiService } from '../services/api';

const ProfilePage: React.FC = () => {
  const theme = useTheme();
  const { user } = useAuth();
  const { showSuccess, showError } = useNotification();
  const { company, logoUrl, uploadLogo, deleteLogo } = useCompany();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [deletingLogo, setDeletingLogo] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [savingCompany, setSavingCompany] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (company) {
      setCompanyName(company.name);
    }
  }, [company]);

  const handleLogoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const maxSizeKB = 500;
    if (file.size > maxSizeKB * 1024) {
      showError(`Arquivo muito grande. Maximo: ${maxSizeKB}KB`);
      return;
    }

    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      showError('Formato nao permitido. Use: PNG, JPG, SVG ou WebP');
      return;
    }

    setUploadingLogo(true);
    try {
      await uploadLogo(file);
      showSuccess('Logo atualizado com sucesso');
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao enviar logo');
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = '';
    }
  };

  const handleDeleteLogo = async () => {
    setDeletingLogo(true);
    try {
      await deleteLogo();
      showSuccess('Logo removido');
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao remover logo');
    } finally {
      setDeletingLogo(false);
    }
  };

  const handleSaveCompany = async () => {
    if (!companyName.trim()) {
      showError('Nome da empresa e obrigatorio');
      return;
    }
    setSavingCompany(true);
    try {
      await apiService.updateMyCompany({ name: companyName.trim() });
      showSuccess('Empresa atualizada com sucesso');
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao atualizar empresa');
    } finally {
      setSavingCompany(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword.length < 6) {
      showError('A nova senha deve ter pelo menos 6 caracteres');
      return;
    }
    if (newPassword !== confirmPassword) {
      showError('As senhas nao coincidem');
      return;
    }

    setChangingPassword(true);
    try {
      await apiService.changePassword(currentPassword, newPassword);
      showSuccess('Senha alterada com sucesso');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao alterar senha');
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Meu Perfil
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Gerencie suas informacoes pessoais e credenciais de acesso
      </Typography>

      <Grid container spacing={3}>
        {/* Profile Info */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent sx={{ textAlign: 'center', py: 4 }}>
              <Avatar
                sx={{
                  width: 96,
                  height: 96,
                  mx: 'auto',
                  mb: 2,
                  bgcolor: 'primary.main',
                  fontSize: '2.5rem',
                  fontWeight: 700,
                }}
              >
                {user?.name?.charAt(0).toUpperCase()}
              </Avatar>
              <Typography variant="h5" fontWeight={700}>
                {user?.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {user?.email}
              </Typography>
              <Box display="flex" justifyContent="center" gap={1} mt={2}>
                <Chip
                  icon={<Shield />}
                  label={user?.is_superuser ? 'Administrador' : 'Usuario'}
                  color={user?.is_superuser ? 'primary' : 'default'}
                  variant="outlined"
                />
                <Chip
                  label={user?.status || 'Ativo'}
                  color="success"
                  variant="outlined"
                />
              </Box>
            </CardContent>
          </Card>

          <Card sx={{ mt: 3 }}>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Informacoes da Conta
              </Typography>
              <Box sx={{ mt: 2 }}>
                <Box display="flex" alignItems="center" gap={1.5} py={1}>
                  <Person fontSize="small" color="action" />
                  <Box>
                    <Typography variant="caption" color="text.secondary">Nome</Typography>
                    <Typography variant="body2" fontWeight={500}>{user?.name}</Typography>
                  </Box>
                </Box>
                <Divider />
                <Box display="flex" alignItems="center" gap={1.5} py={1}>
                  <Email fontSize="small" color="action" />
                  <Box>
                    <Typography variant="caption" color="text.secondary">Email</Typography>
                    <Typography variant="body2" fontWeight={500}>{user?.email}</Typography>
                  </Box>
                </Box>
                <Divider />
                <Box display="flex" alignItems="center" gap={1.5} py={1}>
                  <CalendarToday fontSize="small" color="action" />
                  <Box>
                    <Typography variant="caption" color="text.secondary">Membro desde</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {user?.created_at
                        ? new Date(user.created_at).toLocaleDateString('pt-BR')
                        : '-'}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Change Password */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 4, border: '1px solid', borderColor: 'divider' }}>
            <Box display="flex" alignItems="center" gap={1.5} mb={3}>
              <Box
                sx={{
                  p: 1,
                  borderRadius: 2,
                  bgcolor: alpha(theme.palette.warning.main, 0.1),
                }}
              >
                <Lock color="warning" />
              </Box>
              <Box>
                <Typography variant="h6" fontWeight={600}>
                  Alterar Senha
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Mantenha sua conta segura atualizando sua senha regularmente
                </Typography>
              </Box>
            </Box>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, maxWidth: 500 }}>
              <TextField
                label="Senha Atual"
                type={showPasswords ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                fullWidth
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Lock fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        onClick={() => setShowPasswords(!showPasswords)}
                      >
                        {showPasswords ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <TextField
                label="Nova Senha"
                type={showPasswords ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                fullWidth
                helperText="Minimo de 6 caracteres"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Lock fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                }}
              />
              <TextField
                label="Confirmar Nova Senha"
                type={showPasswords ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                fullWidth
                error={confirmPassword.length > 0 && newPassword !== confirmPassword}
                helperText={
                  confirmPassword.length > 0 && newPassword !== confirmPassword
                    ? 'As senhas nao coincidem'
                    : ''
                }
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Lock fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                }}
              />
              <Button
                variant="contained"
                startIcon={<Save />}
                onClick={handleChangePassword}
                disabled={
                  changingPassword ||
                  !currentPassword ||
                  !newPassword ||
                  newPassword !== confirmPassword
                }
                sx={{ alignSelf: 'flex-start', mt: 1 }}
              >
                {changingPassword ? 'Alterando...' : 'Alterar Senha'}
              </Button>
            </Box>
          </Paper>

          {/* Company Branding */}
          {company && (
            <Paper sx={{ p: 4, mt: 3, border: '1px solid', borderColor: 'divider' }}>
              <Box display="flex" alignItems="center" gap={1.5} mb={3}>
                <Box
                  sx={{
                    p: 1,
                    borderRadius: 2,
                    bgcolor: alpha(theme.palette.primary.main, 0.1),
                  }}
                >
                  <Business color="primary" />
                </Box>
                <Box>
                  <Typography variant="h6" fontWeight={600}>
                    Personalizacao da Empresa
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Personalize o portal com o logo e nome da sua empresa
                  </Typography>
                </Box>
              </Box>

              <Grid container spacing={3}>
                {/* Company Name */}
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Nome da Empresa"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    fullWidth
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Business fontSize="small" color="action" />
                        </InputAdornment>
                      ),
                    }}
                  />
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={savingCompany ? <CircularProgress size={16} /> : <Save />}
                    onClick={handleSaveCompany}
                    disabled={savingCompany || companyName === company.name}
                    sx={{ mt: 1 }}
                  >
                    Salvar Nome
                  </Button>
                </Grid>

                {/* Logo Upload */}
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                    Logo da Empresa
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" mb={2}>
                    O logo aparece na barra lateral do portal. Formatos: PNG, JPG, SVG, WebP (max 500KB)
                  </Typography>

                  <Box display="flex" alignItems="center" gap={2}>
                    {/* Logo Preview */}
                    <Box
                      sx={{
                        width: 80,
                        height: 80,
                        borderRadius: 2,
                        border: '2px dashed',
                        borderColor: logoUrl ? 'primary.main' : 'divider',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                        bgcolor: logoUrl ? 'transparent' : 'action.hover',
                      }}
                    >
                      {logoUrl ? (
                        <Box
                          component="img"
                          src={logoUrl}
                          alt="Logo"
                          sx={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                        />
                      ) : (
                        <Image sx={{ fontSize: 32, color: 'text.disabled' }} />
                      )}
                    </Box>

                    {/* Actions */}
                    <Box display="flex" flexDirection="column" gap={1}>
                      <input
                        type="file"
                        ref={logoInputRef}
                        onChange={handleLogoUpload}
                        accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
                        style={{ display: 'none' }}
                      />
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={uploadingLogo ? <CircularProgress size={16} color="inherit" /> : <CloudUpload />}
                        onClick={() => logoInputRef.current?.click()}
                        disabled={uploadingLogo}
                      >
                        {logoUrl ? 'Trocar Logo' : 'Enviar Logo'}
                      </Button>
                      {logoUrl && (
                        <Button
                          variant="outlined"
                          size="small"
                          color="error"
                          startIcon={deletingLogo ? <CircularProgress size={16} /> : <Delete />}
                          onClick={handleDeleteLogo}
                          disabled={deletingLogo}
                        >
                          Remover
                        </Button>
                      )}
                    </Box>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default ProfilePage;
