import React from 'react';
import { Navigate } from 'react-router-dom';
import { Box, Paper, Typography, Button } from '@mui/material';
import { Lock } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

interface AdminGuardProps {
  children: React.ReactElement;
}

const AdminGuard: React.FC<AdminGuardProps> = ({ children }) => {
  const { user, isSuperuser } = useAuth();

  if (!user) {
    return <Navigate to="/login" />;
  }

  if (!isSuperuser) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px" p={3}>
        <Paper sx={{ p: 4, maxWidth: 400, textAlign: 'center' }}>
          <Lock sx={{ fontSize: 64, color: 'warning.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Acesso Restrito
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Voce nao tem permissao para acessar esta pagina. Apenas administradores podem visualizar este conteudo.
          </Typography>
          <Button variant="contained" href="/dashboard">
            Voltar ao Dashboard
          </Button>
        </Paper>
      </Box>
    );
  }

  return children;
};

export default AdminGuard;
