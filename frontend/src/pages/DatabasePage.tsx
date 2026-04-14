import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
  Chip,
  Divider,
  CircularProgress,
  useTheme,
} from '@mui/material';
import {
  Storage,
  DeleteForever,
  Refresh,
  Warning,
  CheckCircle,
  People,
  Description,
  DataArray,
  WorkOutline,
  Chat,
  History,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';

interface DatabaseStats {
  total_candidates: number;
  total_documents: number;
  total_chunks: number;
  total_embeddings: number;
  total_experiences: number;
  total_profiles: number;
  total_users: number;
  total_audit_logs: number;
  total_conversations: number;
  total_messages: number;
  storage_size_mb: number;
}

const DatabasePage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [stats, setStats] = useState<DatabaseStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [cleaning, setCleaning] = useState(false);
  const [cleanupOptions, setCleanupOptions] = useState({
    delete_candidates: true,
    delete_documents: true,
    delete_chunks: true,
    delete_experiences: true,
    delete_chat_history: false,
    delete_audit_logs: false,
    reset_sequences: true,
  });

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiService.getDatabaseStats();
      setStats(data);
    } catch (error) {
      console.error('Error fetching stats:', error);
      showError('Erro ao carregar estatisticas do banco');
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleCleanup = async () => {
    if (confirmText !== 'CONFIRMAR') {
      showError('Digite CONFIRMAR para executar a limpeza');
      return;
    }

    try {
      setCleaning(true);
      const result = await apiService.cleanupDatabase({
        ...cleanupOptions,
        confirm: 'CONFIRMAR',
      });
      showSuccess(result.message);
      setCleanupDialogOpen(false);
      setConfirmText('');
      fetchStats();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao limpar banco de dados');
    } finally {
      setCleaning(false);
    }
  };

  const statCards = stats ? [
    { label: 'Candidatos', value: stats.total_candidates, icon: <People />, color: theme.palette.primary.main },
    { label: 'Documentos', value: stats.total_documents, icon: <Description />, color: theme.palette.secondary.main },
    { label: 'Chunks', value: stats.total_chunks, icon: <DataArray />, color: theme.palette.info.main },
    { label: 'Embeddings', value: stats.total_embeddings, icon: <DataArray />, color: theme.palette.warning.main },
    { label: 'Experiencias', value: stats.total_experiences, icon: <WorkOutline />, color: theme.palette.success.main },
    { label: 'Conversas', value: stats.total_conversations, icon: <Chat />, color: theme.palette.error.main },
    { label: 'Audit Logs', value: stats.total_audit_logs, icon: <History />, color: '#9c27b0' },
    { label: 'Storage', value: `${stats.storage_size_mb} MB`, icon: <Storage />, color: '#795548' },
  ] : [];

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Gerenciamento do Banco de Dados
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Estatisticas, limpeza e gerenciamento de dados do sistema
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={fetchStats}
          disabled={loading}
        >
          Atualizar
        </Button>
      </Box>

      {/* Stats Grid */}
      {loading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <Grid container spacing={2} sx={{ mb: 4 }}>
            {statCards.map((card) => (
              <Grid item xs={6} sm={4} md={3} key={card.label}>
                <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
                  <CardContent sx={{ textAlign: 'center', py: 2 }}>
                    <Box sx={{ color: card.color, mb: 1 }}>{card.icon}</Box>
                    <Typography variant="h5" fontWeight={700}>
                      {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {card.label}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {/* Actions */}
          <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Acoes de Manutencao
            </Typography>

            <Alert severity="warning" sx={{ mb: 3 }}>
              <Typography variant="body2">
                <strong>Atencao:</strong> As operacoes abaixo sao irreversiveis.
                Faca backup dos dados antes de executar qualquer limpeza.
              </Typography>
            </Alert>

            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Card sx={{ border: '1px solid', borderColor: 'error.main', height: '100%' }}>
                  <CardContent>
                    <Box display="flex" alignItems="center" gap={1} mb={2}>
                      <DeleteForever color="error" />
                      <Typography variant="h6" fontWeight={600}>
                        Limpar Banco de Dados
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Remove candidatos, documentos, curriculos e todos os dados
                      processados. Reseta contadores de ID para recomecar do zero.
                    </Typography>
                    <Button
                      variant="contained"
                      color="error"
                      startIcon={<DeleteForever />}
                      onClick={() => setCleanupDialogOpen(true)}
                      disabled={stats?.total_candidates === 0 && stats?.total_documents === 0}
                    >
                      Limpar Dados
                    </Button>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card sx={{ border: '1px solid', borderColor: 'divider', height: '100%' }}>
                  <CardContent>
                    <Box display="flex" alignItems="center" gap={1} mb={2}>
                      <Refresh color="primary" />
                      <Typography variant="h6" fontWeight={600}>
                        Reprocessar Embeddings
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Regenera os embeddings vetoriais de todos os documentos.
                      Util apos atualizar o modelo de embeddings.
                    </Typography>
                    <Button
                      variant="outlined"
                      color="primary"
                      startIcon={<Refresh />}
                      onClick={async () => {
                        try {
                          await apiService.refreshEmbeddings();
                          showSuccess('Embeddings estao sendo regenerados');
                        } catch (err: any) {
                          showError(err.response?.data?.detail || 'Erro ao regenerar embeddings');
                        }
                      }}
                      disabled={stats?.total_chunks === 0}
                    >
                      Regenerar Embeddings
                    </Button>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Paper>
        </>
      )}

      {/* Cleanup Dialog */}
      <Dialog
        open={cleanupDialogOpen}
        onClose={() => {
          setCleanupDialogOpen(false);
          setConfirmText('');
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <Warning color="error" />
            <Typography variant="h6">Limpar Banco de Dados</Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 3 }}>
            Esta operacao e <strong>irreversivel</strong>! Todos os dados selecionados serao
            permanentemente removidos.
          </Alert>

          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Selecione o que deseja remover:
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 3 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.delete_candidates}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, delete_candidates: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Candidatos e dados associados</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats?.total_candidates || 0} candidato(s), perfis, consentimentos
                  </Typography>
                </Box>
              }
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.delete_documents}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, delete_documents: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Documentos e arquivos</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats?.total_documents || 0} documento(s), {stats?.storage_size_mb || 0} MB
                  </Typography>
                </Box>
              }
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.delete_chunks}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, delete_chunks: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Chunks e embeddings vetoriais</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats?.total_chunks || 0} chunk(s), {stats?.total_embeddings || 0} embedding(s)
                  </Typography>
                </Box>
              }
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.delete_experiences}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, delete_experiences: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Experiencias profissionais</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats?.total_experiences || 0} experiencia(s)
                  </Typography>
                </Box>
              }
            />

            <Divider sx={{ my: 1 }} />

            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.delete_chat_history}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, delete_chat_history: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Historico de chat</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats?.total_conversations || 0} conversa(s), {stats?.total_messages || 0} mensagem(ns)
                  </Typography>
                </Box>
              }
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.delete_audit_logs}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, delete_audit_logs: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Logs de auditoria</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats?.total_audit_logs || 0} registro(s)
                  </Typography>
                </Box>
              }
            />

            <Divider sx={{ my: 1 }} />

            <FormControlLabel
              control={
                <Checkbox
                  checked={cleanupOptions.reset_sequences}
                  onChange={(e) => setCleanupOptions(prev => ({ ...prev, reset_sequences: e.target.checked }))}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Resetar contadores de ID</Typography>
                  <Typography variant="caption" color="text.secondary">
                    IDs voltam a comecar do 1
                  </Typography>
                </Box>
              }
            />
          </Box>

          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Para confirmar, digite CONFIRMAR:
          </Typography>
          <TextField
            fullWidth
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="CONFIRMAR"
            size="small"
            error={confirmText.length > 0 && confirmText !== 'CONFIRMAR'}
            helperText={confirmText.length > 0 && confirmText !== 'CONFIRMAR' ? 'Digite exatamente CONFIRMAR' : ''}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setCleanupDialogOpen(false);
              setConfirmText('');
            }}
          >
            Cancelar
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleCleanup}
            disabled={confirmText !== 'CONFIRMAR' || cleaning}
            startIcon={cleaning ? <CircularProgress size={16} /> : <DeleteForever />}
          >
            {cleaning ? 'Limpando...' : 'Executar Limpeza'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DatabasePage;
