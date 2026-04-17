import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Chip,
  Button,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Divider,
  LinearProgress,
  MenuItem,
  Select,
  FormControl,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import { ArrowBack, ContentCopy, Edit, OpenInNew } from '@mui/icons-material';
import { apiService } from '../services/api';
import { Job, JobApplication, JobFitAnalysis } from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { useCompany } from '../contexts/CompanyContext';

const STAGES = ['received', 'screening', 'interview', 'technical', 'offer', 'hired', 'rejected'];
const STAGE_LABELS: Record<string, string> = {
  received: 'Recebida',
  screening: 'Triagem',
  interview: 'Entrevista',
  technical: 'Tecnica',
  offer: 'Oferta',
  hired: 'Contratado',
  rejected: 'Descartado',
};

const RECOMMENDATION_COLORS: Record<string, 'success' | 'info' | 'warning' | 'error'> = {
  strong_match: 'success',
  good_match: 'info',
  weak_match: 'warning',
  no_match: 'error',
};

const RECOMMENDATION_LABELS: Record<string, string> = {
  strong_match: 'Match excelente',
  good_match: 'Bom match',
  weak_match: 'Match fraco',
  no_match: 'Sem fit',
};

const JobDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { company } = useCompany();
  const { showError, showSuccess } = useNotification();

  const [job, setJob] = useState<Job | null>(null);
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedApp, setSelectedApp] = useState<JobApplication | null>(null);

  useEffect(() => {
    if (id) {
      fetchData(parseInt(id));
    }
  }, [id]);

  const fetchData = async (jobId: number) => {
    try {
      setLoading(true);
      const [j, a] = await Promise.all([
        apiService.getJob(jobId),
        apiService.listJobApplications(jobId),
      ]);
      setJob(j);
      setApplications(a);
    } catch (err) {
      showError('Erro ao carregar dados da vaga');
    } finally {
      setLoading(false);
    }
  };

  const handleStageChange = async (appId: number, newStage: string) => {
    if (!id) return;
    try {
      await apiService.updateApplicationStage(parseInt(id), appId, newStage);
      showSuccess('Estagio atualizado');
      fetchData(parseInt(id));
    } catch (err) {
      showError('Erro ao atualizar estagio');
    }
  };

  const copyPublicLink = () => {
    if (!company?.slug || !job?.slug) return;
    const url = `${window.location.origin}/careers/${company.slug}/${job.slug}`;
    navigator.clipboard.writeText(url);
    showSuccess('Link publico copiado');
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (!job) {
    return <Typography>Vaga nao encontrada</Typography>;
  }

  const fitAnalysis = (selectedApp?.fit_analysis as JobFitAnalysis | undefined) || {};

  return (
    <Box className="fade-in">
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Tooltip title="Voltar">
          <IconButton onClick={() => navigate('/jobs')}>
            <ArrowBack />
          </IconButton>
        </Tooltip>
        <Box flexGrow={1}>
          <Typography variant="h4" fontWeight={700}>
            {job.title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {job.location || 'Sem localizacao'} · {job.work_mode || '-'} · {job.employment_type || '-'}
          </Typography>
        </Box>
        <Tooltip title="Ver pagina publica">
          <IconButton
            onClick={() =>
              company?.slug && window.open(`/careers/${company.slug}/${job.slug}`, '_blank')
            }
          >
            <OpenInNew />
          </IconButton>
        </Tooltip>
        <Tooltip title="Copiar link publico">
          <IconButton onClick={copyPublicLink}>
            <ContentCopy />
          </IconButton>
        </Tooltip>
        <Button
          variant="outlined"
          startIcon={<Edit />}
          onClick={() => navigate(`/jobs/${job.id}/edit`)}
        >
          Editar
        </Button>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, border: '1px solid', borderColor: 'divider', mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Resumo da vaga
            </Typography>
            <Divider sx={{ my: 1 }} />
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {job.description}
            </Typography>
          </Paper>

          {(job.skills_required?.length || 0) > 0 && (
            <Paper sx={{ p: 2, border: '1px solid', borderColor: 'divider', mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Skills exigidas
              </Typography>
              <Box display="flex" gap={0.5} flexWrap="wrap">
                {job.skills_required.map((s) => (
                  <Chip key={s} label={s} size="small" />
                ))}
              </Box>
            </Paper>
          )}
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ border: '1px solid', borderColor: 'divider' }}>
            <Box p={2} display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="h6">Aplicacoes ({applications.length})</Typography>
              <Chip
                label={job.is_active ? 'Vaga ativa' : 'Vaga inativa'}
                color={job.is_active ? 'success' : 'default'}
                size="small"
              />
            </Box>
            <Divider />
            {applications.length === 0 ? (
              <Box p={4} textAlign="center">
                <Typography color="text.secondary">
                  Ainda nao ha candidaturas nesta vaga
                </Typography>
              </Box>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Candidato</TableCell>
                      <TableCell>Email</TableCell>
                      <TableCell align="center">Fit</TableCell>
                      <TableCell>Recomendacao</TableCell>
                      <TableCell>Estagio</TableCell>
                      <TableCell align="right">Acoes</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {applications.map((app) => (
                      <TableRow key={app.id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {app.applicant_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(app.created_at).toLocaleDateString('pt-BR')}
                          </Typography>
                        </TableCell>
                        <TableCell>{app.applicant_email}</TableCell>
                        <TableCell align="center">
                          {app.fit_status === 'pending' ? (
                            <Box sx={{ minWidth: 80 }}>
                              <LinearProgress />
                              <Typography variant="caption">Analisando</Typography>
                            </Box>
                          ) : app.fit_status === 'failed' ? (
                            <Chip label="Falha" size="small" color="error" />
                          ) : (
                            <Typography fontWeight={700}>
                              {app.fit_score ?? '-'}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          {app.fit_analysis?.recommendation ? (
                            <Chip
                              size="small"
                              label={RECOMMENDATION_LABELS[app.fit_analysis.recommendation]}
                              color={RECOMMENDATION_COLORS[app.fit_analysis.recommendation]}
                            />
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell>
                          <FormControl size="small" sx={{ minWidth: 130 }}>
                            <Select
                              value={app.stage}
                              onChange={(e) => handleStageChange(app.id, e.target.value)}
                            >
                              {STAGES.map((s) => (
                                <MenuItem key={s} value={s}>
                                  {STAGE_LABELS[s]}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </TableCell>
                        <TableCell align="right">
                          <Button size="small" onClick={() => setSelectedApp(app)}>
                            Ver fit
                          </Button>
                          <Button
                            size="small"
                            onClick={() => navigate(`/candidates/${app.candidate_id}`)}
                          >
                            Perfil
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Dialog
        open={!!selectedApp}
        onClose={() => setSelectedApp(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Analise de fit — {selectedApp?.applicant_name}
        </DialogTitle>
        <DialogContent dividers>
          {selectedApp?.fit_status !== 'analyzed' ? (
            <Typography color="text.secondary">
              {selectedApp?.fit_status === 'pending'
                ? 'Analise em andamento. Recarregue a pagina em alguns instantes.'
                : 'Analise de fit nao disponivel.'}
            </Typography>
          ) : (
            <Box>
              <Box display="flex" gap={2} alignItems="center" mb={2}>
                <Typography variant="h3" color="primary">
                  {selectedApp.fit_score}
                </Typography>
                <Box>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {RECOMMENDATION_LABELS[fitAnalysis.recommendation || '']}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {fitAnalysis.summary}
                  </Typography>
                </Box>
              </Box>

              {(fitAnalysis.strengths?.length || 0) > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" color="success.main" gutterBottom>
                    Pontos fortes
                  </Typography>
                  <List dense>
                    {fitAnalysis.strengths!.map((s, i) => (
                      <ListItem key={i} sx={{ py: 0 }}>
                        <ListItemText primary={`• ${s}`} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              {(fitAnalysis.gaps?.length || 0) > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" color="warning.main" gutterBottom>
                    Gaps
                  </Typography>
                  <List dense>
                    {fitAnalysis.gaps!.map((g, i) => (
                      <ListItem key={i} sx={{ py: 0 }}>
                        <ListItemText primary={`• ${g}`} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              <Grid container spacing={2}>
                {(fitAnalysis.matched_skills?.length || 0) > 0 && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="subtitle2" gutterBottom>
                      Skills que atendem
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap">
                      {fitAnalysis.matched_skills!.map((s) => (
                        <Chip key={s} label={s} color="success" size="small" />
                      ))}
                    </Box>
                  </Grid>
                )}
                {(fitAnalysis.missing_skills?.length || 0) > 0 && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="subtitle2" gutterBottom>
                      Skills faltantes
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap">
                      {fitAnalysis.missing_skills!.map((s) => (
                        <Chip key={s} label={s} color="warning" size="small" />
                      ))}
                    </Box>
                  </Grid>
                )}
              </Grid>

              {fitAnalysis.experience_match && (
                <Box mt={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    Experiencia
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {fitAnalysis.experience_match}
                  </Typography>
                </Box>
              )}

              {selectedApp.cover_letter && (
                <Box mt={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    Mensagem do candidato
                  </Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {selectedApp.cover_letter}
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedApp(null)}>Fechar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default JobDetailPage;
