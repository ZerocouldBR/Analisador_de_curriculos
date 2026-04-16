import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  TextField,
  Tooltip,
  Typography,
  Chip,
  Divider,
  InputAdornment,
  CircularProgress,
} from '@mui/material';
import { ContentCopy, Delete, Link as LinkIcon } from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';
import { AccessTokenListItem, CandidateAccessToken } from '../types';

interface Props {
  candidateId: number;
  open: boolean;
  onClose: () => void;
}

const CandidateAccessTokenDialog: React.FC<Props> = ({ candidateId, open, onClose }) => {
  const { showError, showSuccess } = useNotification();
  const [tokens, setTokens] = useState<AccessTokenListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<CandidateAccessToken | null>(null);
  const [expiresInHours, setExpiresInHours] = useState<number>(72);

  useEffect(() => {
    if (open) {
      fetchTokens();
      setGenerated(null);
    }
  }, [open, candidateId]);

  const fetchTokens = async () => {
    try {
      setLoading(true);
      const list = await apiService.listCandidateAccessTokens(candidateId);
      setTokens(list);
    } catch {
      showError('Erro ao carregar tokens');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      const token = await apiService.generateCandidateAccessToken(candidateId, expiresInHours);
      setGenerated(token);
      showSuccess('Link gerado com sucesso');
      fetchTokens();
    } catch {
      showError('Erro ao gerar link');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = (url: string) => {
    navigator.clipboard.writeText(url);
    showSuccess('Link copiado');
  };

  const handleRevoke = async (tokenId: number) => {
    try {
      await apiService.revokeCandidateAccessToken(candidateId, tokenId);
      showSuccess('Link revogado');
      fetchTokens();
    } catch {
      showError('Erro ao revogar link');
    }
  };

  const formatDate = (d?: string) => (d ? new Date(d).toLocaleString('pt-BR') : '-');

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Link de acesso do candidato</DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Gere um link magico para o candidato acessar e editar o proprio perfil,
          com sugestoes de melhoria por IA. Envie este link por email ou WhatsApp.
        </Typography>

        <Box display="flex" gap={1} alignItems="center" mt={2}>
          <TextField
            label="Validade"
            type="number"
            size="small"
            value={expiresInHours}
            onChange={(e) => setExpiresInHours(Math.max(1, Number(e.target.value) || 72))}
            InputProps={{ endAdornment: <InputAdornment position="end">horas</InputAdornment> }}
            sx={{ width: 180 }}
          />
          <Button
            variant="contained"
            onClick={handleGenerate}
            disabled={generating}
            startIcon={<LinkIcon />}
          >
            {generating ? 'Gerando...' : 'Gerar novo link'}
          </Button>
        </Box>

        {generated && (
          <Box mt={2} p={2} sx={{ bgcolor: 'action.hover', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Link gerado (valido ate {formatDate(generated.expires_at)})
            </Typography>
            <Box display="flex" alignItems="center" gap={1} mt={1}>
              <TextField
                value={generated.url}
                size="small"
                fullWidth
                InputProps={{ readOnly: true }}
                onFocus={(e) => e.target.select()}
              />
              <Tooltip title="Copiar">
                <IconButton onClick={() => handleCopy(generated.url)}>
                  <ContentCopy />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        <Typography variant="subtitle2" gutterBottom>
          Links anteriores
        </Typography>
        {loading ? (
          <Box display="flex" justifyContent="center" p={2}>
            <CircularProgress size={24} />
          </Box>
        ) : tokens.length === 0 ? (
          <Typography variant="caption" color="text.secondary">
            Nenhum link gerado ainda
          </Typography>
        ) : (
          <List dense>
            {tokens.map((t) => {
              const isRevoked = !!t.revoked_at;
              const isExpired = new Date(t.expires_at) < new Date();
              return (
                <ListItem
                  key={t.id}
                  secondaryAction={
                    !isRevoked && !isExpired ? (
                      <Tooltip title="Revogar">
                        <IconButton edge="end" onClick={() => handleRevoke(t.id)}>
                          <Delete />
                        </IconButton>
                      </Tooltip>
                    ) : null
                  }
                >
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="body2">
                          Criado em {formatDate(t.created_at)}
                        </Typography>
                        {isRevoked && <Chip size="small" label="Revogado" color="error" />}
                        {!isRevoked && isExpired && <Chip size="small" label="Expirado" />}
                        {!isRevoked && !isExpired && (
                          <Chip size="small" label="Ativo" color="success" />
                        )}
                      </Box>
                    }
                    secondary={
                      <>
                        Expira em {formatDate(t.expires_at)} ·{' '}
                        {t.use_count} uso{t.use_count === 1 ? '' : 's'}
                      </>
                    }
                  />
                </ListItem>
              );
            })}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Fechar</Button>
      </DialogActions>
    </Dialog>
  );
};

export default CandidateAccessTokenDialog;
