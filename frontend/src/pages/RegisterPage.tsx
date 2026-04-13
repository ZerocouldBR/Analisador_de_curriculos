import React, { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Link,
  Alert,
  InputAdornment,
  IconButton,
  useTheme,
  Divider,
  Collapse,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  Email,
  Lock,
  Person,
  SmartToy,
  Business,
  Phone,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const RegisterPage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showCompanyFields, setShowCompanyFields] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [companyCnpj, setCompanyCnpj] = useState('');
  const [companyPhone, setCompanyPhone] = useState('');
  const { register } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres');
      return;
    }
    if (!/[A-Z]/.test(password)) {
      setError('A senha deve conter pelo menos uma letra maiuscula');
      return;
    }
    if (!/[a-z]/.test(password)) {
      setError('A senha deve conter pelo menos uma letra minuscula');
      return;
    }
    if (!/\d/.test(password)) {
      setError('A senha deve conter pelo menos um numero');
      return;
    }
    if (!/[!@#$%^&*(),.?":{}|<>_\-+=[\]\\;/~`]/.test(password)) {
      setError('A senha deve conter pelo menos um caractere especial');
      return;
    }

    if (password !== confirmPassword) {
      setError('As senhas nao coincidem');
      return;
    }

    setLoading(true);

    try {
      const registerData: any = { name, email, password };

      if (showCompanyFields && companyName.trim()) {
        registerData.company_name = companyName.trim();
        if (companyCnpj.trim()) registerData.company_cnpj = companyCnpj.trim();
        if (companyPhone.trim()) registerData.company_phone = companyPhone.trim();
      }

      await register(registerData);
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg || String(d)).join('; '));
      } else {
        setError('Erro ao criar conta. Tente novamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: theme.palette.mode === 'light'
          ? 'linear-gradient(135deg, #1565c0 0%, #0d47a1 50%, #1a237e 100%)'
          : 'linear-gradient(135deg, #0d47a1 0%, #1a237e 100%)',
        p: 3,
      }}
    >
      <Paper
        elevation={8}
        sx={{
          p: 5,
          width: '100%',
          maxWidth: 520,
          borderRadius: 3,
        }}
      >
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <SmartToy sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
          <Typography variant="h5" fontWeight={700} gutterBottom>
            Criar Conta
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Cadastre-se para acessar o sistema de analise de curriculos
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="Nome Completo"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            autoComplete="name"
            sx={{ mb: 2.5 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Person color="action" fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            sx={{ mb: 2.5 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Email color="action" fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <TextField
            fullWidth
            label="Senha"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
            sx={{ mb: 2.5 }}
            helperText="Minimo 8 caracteres, com maiuscula, minuscula, numero e especial"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Lock color="action" fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword(!showPassword)}
                    edge="end"
                    size="small"
                  >
                    {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <TextField
            fullWidth
            label="Confirmar Senha"
            type={showPassword ? 'text' : 'password'}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
            sx={{ mb: 3 }}
            error={confirmPassword.length > 0 && password !== confirmPassword}
            helperText={
              confirmPassword.length > 0 && password !== confirmPassword
                ? 'As senhas nao coincidem'
                : ''
            }
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Lock color="action" fontSize="small" />
                </InputAdornment>
              ),
            }}
          />

          {/* Secao de empresa */}
          <Divider sx={{ mb: 2 }} />
          <Button
            fullWidth
            variant="text"
            size="small"
            onClick={() => setShowCompanyFields(!showCompanyFields)}
            endIcon={showCompanyFields ? <ExpandLess /> : <ExpandMore />}
            startIcon={<Business />}
            sx={{ mb: 1, justifyContent: 'flex-start', textTransform: 'none' }}
          >
            {showCompanyFields ? 'Ocultar dados da empresa' : 'Cadastrar empresa de RH (opcional)'}
          </Button>
          <Collapse in={showCompanyFields}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                Cadastre sua empresa para gerenciar candidatos de forma isolada. Voce sera o administrador.
              </Typography>
              <TextField
                fullWidth
                label="Nome da Empresa"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                sx={{ mb: 2 }}
                placeholder="Ex: RH Solutions Ltda"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Business color="action" fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              <Box display="flex" gap={2}>
                <TextField
                  fullWidth
                  label="CNPJ"
                  value={companyCnpj}
                  onChange={(e) => setCompanyCnpj(e.target.value)}
                  placeholder="00.000.000/0001-00"
                />
                <TextField
                  fullWidth
                  label="Telefone"
                  value={companyPhone}
                  onChange={(e) => setCompanyPhone(e.target.value)}
                  placeholder="(00) 00000-0000"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Phone color="action" fontSize="small" />
                      </InputAdornment>
                    ),
                  }}
                />
              </Box>
            </Box>
          </Collapse>

          <Button
            type="submit"
            fullWidth
            variant="contained"
            size="large"
            disabled={loading}
            sx={{
              py: 1.5,
              mb: 3,
              fontWeight: 600,
              fontSize: '1rem',
            }}
          >
            {loading ? 'Criando conta...' : 'Cadastrar'}
          </Button>
          <Typography variant="body2" align="center" color="text.secondary">
            Ja tem uma conta?{' '}
            <Link component={RouterLink} to="/login" fontWeight={600}>
              Faca login
            </Link>
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default RegisterPage;
