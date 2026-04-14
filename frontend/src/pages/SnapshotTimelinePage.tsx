import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Button,
  IconButton,
  Tooltip,
  CircularProgress,
  Checkbox,
  Chip,
  Divider,
  Alert,
  useTheme,
  alpha,
} from '@mui/material';
import {
  ArrowBack,
  Compare,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';
import { SnapshotSummary, SnapshotDiff } from '../types';

const SnapshotTimelinePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const { showError } = useNotification();

  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [diff, setDiff] = useState<SnapshotDiff | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);

  const candidateId = id ? parseInt(id) : 0;

  useEffect(() => {
    if (candidateId) fetchSnapshots();
  }, [candidateId]);

  const fetchSnapshots = async () => {
    try {
      setLoading(true);
      const response = await apiService.getCandidateSnapshots(candidateId);
      setSnapshots(response.data);
    } catch (error) {
      showError('Erro ao carregar snapshots');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelect = (snapshotId: number) => {
    setSelectedIds((prev) => {
      if (prev.includes(snapshotId)) {
        return prev.filter((sid) => sid !== snapshotId);
      }
      if (prev.length >= 2) {
        return [prev[1], snapshotId];
      }
      return [...prev, snapshotId];
    });
    setDiff(null);
  };

  const handleCompare = async () => {
    if (selectedIds.length !== 2) return;
    const [fromId, toId] = selectedIds.sort((a, b) => a - b);
    try {
      setLoadingDiff(true);
      const response = await apiService.getSnapshotDiff(candidateId, fromId, toId);
      setDiff(response.data);
    } catch (error) {
      showError('Erro ao comparar snapshots');
    } finally {
      setLoadingDiff(false);
    }
  };

  const truncateHash = (hash: string) => hash.substring(0, 12);

  const getDiffColor = (field: string, change: { from: any; to: any }) => {
    if (change.from === null || change.from === undefined || change.from === '') return 'success';
    if (change.to === null || change.to === undefined || change.to === '') return 'error';
    return 'warning';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress size={48} />
      </Box>
    );
  }

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Tooltip title="Voltar para candidato">
          <IconButton onClick={() => navigate(`/candidates/${candidateId}`)}>
            <ArrowBack />
          </IconButton>
        </Tooltip>
        <Box flexGrow={1}>
          <Typography variant="h4" fontWeight={700}>
            Timeline de Snapshots
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Candidato #{candidateId} - Historico de alteracoes de dados
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Compare />}
          onClick={handleCompare}
          disabled={selectedIds.length !== 2 || loadingDiff}
        >
          {loadingDiff ? <CircularProgress size={20} color="inherit" /> : 'Comparar'}
        </Button>
      </Box>

      {selectedIds.length > 0 && selectedIds.length < 2 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Selecione mais 1 snapshot para comparar
        </Alert>
      )}

      {snapshots.length === 0 ? (
        <Box textAlign="center" py={8}>
          <TimelineIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            Nenhum snapshot encontrado
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Snapshots sao criados automaticamente durante sincronizacoes
          </Typography>
        </Box>
      ) : (
        <Box display="flex" gap={3} flexDirection={{ xs: 'column', md: 'row' }}>
          {/* Timeline */}
          <Box flex={1}>
            <Paper sx={{ border: '1px solid', borderColor: 'divider' }}>
              {snapshots.map((snapshot, index) => (
                <React.Fragment key={snapshot.id}>
                  {index > 0 && <Divider />}
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      p: 2,
                      gap: 2,
                      bgcolor: selectedIds.includes(snapshot.id)
                        ? alpha(theme.palette.primary.main, 0.06)
                        : 'transparent',
                      transition: 'background-color 0.15s',
                      '&:hover': {
                        bgcolor: alpha(theme.palette.primary.main, 0.03),
                      },
                    }}
                  >
                    <Checkbox
                      checked={selectedIds.includes(snapshot.id)}
                      onChange={() => handleToggleSelect(snapshot.id)}
                      size="small"
                    />

                    {/* Timeline dot and line */}
                    <Box
                      sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        position: 'relative',
                      }}
                    >
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          borderRadius: '50%',
                          bgcolor: selectedIds.includes(snapshot.id)
                            ? 'primary.main'
                            : 'grey.400',
                          border: '2px solid',
                          borderColor: selectedIds.includes(snapshot.id)
                            ? 'primary.main'
                            : 'grey.300',
                        }}
                      />
                    </Box>

                    <Box flexGrow={1}>
                      <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                        <Typography variant="body2" fontWeight={600} fontFamily="monospace">
                          {truncateHash(snapshot.snapshot_hash)}
                        </Typography>
                        <Chip
                          label={`#${snapshot.id}`}
                          size="small"
                          variant="outlined"
                        />
                        {index === 0 && (
                          <Chip label="Mais recente" size="small" color="primary" />
                        )}
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(snapshot.created_at).toLocaleString('pt-BR')}
                        {snapshot.source_id && ` | Fonte #${snapshot.source_id}`}
                      </Typography>
                    </Box>
                  </Box>
                </React.Fragment>
              ))}
            </Paper>
          </Box>

          {/* Diff Panel */}
          {diff && (
            <Box flex={1}>
              <Paper sx={{ border: '1px solid', borderColor: 'divider', p: 3 }}>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Diferencas
                </Typography>
                {diff.diff_summary && (
                  <Typography variant="body2" color="text.secondary" mb={2}>
                    {diff.diff_summary}
                  </Typography>
                )}

                {Object.keys(diff.changed_fields).length === 0 ? (
                  <Alert severity="info">Nenhuma diferenca encontrada entre os snapshots</Alert>
                ) : (
                  <Box display="flex" flexDirection="column" gap={2}>
                    {Object.entries(diff.changed_fields).map(([field, change]) => {
                      const color = getDiffColor(field, change);
                      return (
                        <Paper
                          key={field}
                          variant="outlined"
                          sx={{
                            p: 2,
                            borderLeftWidth: 3,
                            borderLeftColor:
                              color === 'success'
                                ? 'success.main'
                                : color === 'error'
                                ? 'error.main'
                                : 'warning.main',
                          }}
                        >
                          <Typography variant="subtitle2" fontWeight={600} mb={1}>
                            {field}
                          </Typography>
                          <Box display="flex" flexDirection="column" gap={0.5}>
                            <Box display="flex" alignItems="flex-start" gap={1}>
                              <Chip
                                label="De"
                                size="small"
                                color="error"
                                variant="outlined"
                                sx={{ minWidth: 40 }}
                              />
                              <Typography
                                variant="body2"
                                sx={{
                                  bgcolor: alpha(theme.palette.error.main, 0.06),
                                  px: 1,
                                  py: 0.5,
                                  borderRadius: 1,
                                  fontFamily: 'monospace',
                                  wordBreak: 'break-all',
                                  flex: 1,
                                }}
                              >
                                {change.from !== null && change.from !== undefined
                                  ? String(change.from)
                                  : '(vazio)'}
                              </Typography>
                            </Box>
                            <Box display="flex" alignItems="flex-start" gap={1}>
                              <Chip
                                label="Para"
                                size="small"
                                color="success"
                                variant="outlined"
                                sx={{ minWidth: 40 }}
                              />
                              <Typography
                                variant="body2"
                                sx={{
                                  bgcolor: alpha(theme.palette.success.main, 0.06),
                                  px: 1,
                                  py: 0.5,
                                  borderRadius: 1,
                                  fontFamily: 'monospace',
                                  wordBreak: 'break-all',
                                  flex: 1,
                                }}
                              >
                                {change.to !== null && change.to !== undefined
                                  ? String(change.to)
                                  : '(vazio)'}
                              </Typography>
                            </Box>
                          </Box>
                        </Paper>
                      );
                    })}
                  </Box>
                )}
              </Paper>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};

export default SnapshotTimelinePage;
