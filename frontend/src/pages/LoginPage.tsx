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
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  Email,
  Lock,
  SmartToy,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login({ email, password });
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg || String(d)).join('; '));
      } else {
        setError('Erro ao fazer login. Verifique suas credenciais.');
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
        background: theme.palette.mode === 'light'
          ? 'linear-gradient(135deg, #1565c0 0%, #0d47a1 50%, #1a237e 100%)'
          : 'linear-gradient(135deg, #0d47a1 0%, #1a237e 100%)',
      }}
    >
      {/* Left side - Branding */}
      <Box
        sx={{
          flex: 1,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          color: 'white',
          px: 6,
        }}
      >
        <SmartToy sx={{ fontSize: 80, mb: 3, opacity: 0.9 }} />
        <Typography variant="h3" fontWeight={700} gutterBottom textAlign="center">
          Analisador de Curriculos
        </Typography>
        <Typography variant="h6" sx={{ opacity: 0.85, maxWidth: 500, textAlign: 'center' }}>
          Sistema inteligente de gestao de talentos com IA para analise, busca semantica e
          matching automatico de candidatos
        </Typography>
        <Box sx={{ mt: 4, display: 'flex', gap: 3 }}>
          {['Busca Semantica', 'Chat com IA', 'Analise Automatica'].map((feature) => (
            <Paper
              key={feature}
              sx={{
                px: 2,
                py: 1,
                bgcolor: 'rgba(255,255,255,0.15)',
                color: 'white',
                backdropFilter: 'blur(10px)',
              }}
            >
              <Typography variant="body2" fontWeight={500}>
                {feature}
              </Typography>
            </Paper>
          ))}
        </Box>
      </Box>

      {/* Right side - Form */}
      <Box
        sx={{
          flex: { xs: 1, md: '0 0 480px' },
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
        }}
      >
        <Paper
          elevation={8}
          sx={{
            p: 5,
            width: '100%',
            maxWidth: 440,
            borderRadius: 3,
          }}
        >
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Box sx={{ display: { xs: 'block', md: 'none' }, mb: 2 }}>
              <SmartToy sx={{ fontSize: 48, color: 'primary.main' }} />
            </Box>
            <Typography variant="h5" fontWeight={700} gutterBottom>
              Bem-vindo de volta
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Entre com suas credenciais para acessar o sistema
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
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
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
              autoComplete="current-password"
              sx={{ mb: 3 }}
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
              {loading ? 'Entrando...' : 'Entrar'}
            </Button>
            <Typography variant="body2" align="center" color="text.secondary">
              Nao tem uma conta?{' '}
              <Link component={RouterLink} to="/register" fontWeight={600}>
                Cadastre-se
              </Link>
            </Typography>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default LoginPage;
