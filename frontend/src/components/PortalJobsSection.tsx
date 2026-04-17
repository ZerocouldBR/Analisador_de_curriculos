import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  LinearProgress,
  Paper,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { CheckCircle, Send } from '@mui/icons-material';
import { apiService } from '../services/api';
import {
  PortalJobListItem,
  PortalMyApplication,
} from '../types';

interface Props {
  token: string;
}

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

const PortalJobsSection: React.FC<Props> = ({ token }) => {
  const [tab, setTab] = useState(0);
  const [jobs, setJobs] = useState<PortalJobListItem[]>([]);
  const [applications, setApplications] = useState<PortalMyApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [applyTarget, setApplyTarget] = useState<PortalJobListItem | null>(null);
  const [coverLetter, setCoverLetter] = useState('');
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [j, a] = await Promise.all([
        apiService.listPortalJobs(token),
        apiService.listPortalMyApplications(token),
      ]);
      setJobs(j.jobs);
      setApplications(a.applications);
    } catch (err: any) {
      // nao bloquear portal se essa secao falhar
      setError(err?.response?.data?.detail || 'Nao foi possivel carregar vagas');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!applyTarget) return;
    try {
      setApplying(true);
      const res = await apiService.applyFromPortal(
        token,
        applyTarget.slug,
        coverLetter || undefined,
      );
      setSuccessMsg(res.message);
      setApplyTarget(null);
      setCoverLetter('');
      fetchAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao aplicar');
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} gutterBottom>
          Vagas abertas
        </Typography>
        <Box display="flex" justifyContent="center" p={2}>
          <CircularProgress size={24} />
        </Box>
      </Paper>
    );
  }

  if (jobs.length === 0 && applications.length === 0) {
    return null;
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Vagas abertas (${jobs.length})`} />
        <Tab label={`Minhas candidaturas (${applications.length})`} />
      </Tabs>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {successMsg && (
        <Alert
          severity="success"
          icon={<CheckCircle />}
          sx={{ mb: 2 }}
          onClose={() => setSuccessMsg(null)}
        >
          {successMsg}
        </Alert>
      )}

      {tab === 0 && (
        <>
          {jobs.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Nenhuma vaga aberta no momento
            </Typography>
          ) : (
            jobs.map((job) => (
              <Box
                key={job.slug}
                sx={{
                  py: 2,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  '&:last-child': { borderBottom: 'none' },
                }}
              >
                <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                  <Box flexGrow={1}>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {job.title}
                    </Typography>
                    <Box display="flex" flexWrap="wrap" gap={0.5} mt={0.5}>
                      {job.location && <Chip size="small" label={job.location} />}
                      {job.work_mode && (
                        <Chip size="small" label={job.work_mode} variant="outlined" />
                      )}
                      {job.employment_type && (
                        <Chip size="small" label={job.employment_type} variant="outlined" />
                      )}
                      {job.seniority_level && (
                        <Chip size="small" label={job.seniority_level} variant="outlined" />
                      )}
                    </Box>
                    {job.salary_display && (
                      <Typography variant="body2" color="primary" mt={0.5}>
                        {job.salary_display}
                      </Typography>
                    )}
                  </Box>
                  <Box>
                    {job.already_applied ? (
                      <Chip
                        icon={<CheckCircle />}
                        color="success"
                        size="small"
                        label={`Aplicado (${STAGE_LABELS[job.my_application_stage || ''] || job.my_application_stage})`}
                      />
                    ) : (
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={<Send />}
                        onClick={() => {
                          setApplyTarget(job);
                          setCoverLetter('');
                        }}
                      >
                        Aplicar
                      </Button>
                    )}
                  </Box>
                </Box>
              </Box>
            ))
          )}
        </>
      )}

      {tab === 1 && (
        <>
          {applications.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Voce ainda nao aplicou a nenhuma vaga desta empresa
            </Typography>
          ) : (
            applications.map((app) => (
              <Box
                key={app.id}
                sx={{
                  py: 2,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  '&:last-child': { borderBottom: 'none' },
                }}
              >
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box flexGrow={1}>
                    <Typography variant="subtitle2" fontWeight={600}>
                      {app.job_title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Aplicado em {new Date(app.created_at).toLocaleDateString('pt-BR')}
                    </Typography>
                  </Box>
                  <Box display="flex" gap={1} alignItems="center">
                    <Chip
                      size="small"
                      label={STAGE_LABELS[app.stage] || app.stage}
                    />
                    {app.fit_status === 'pending' && (
                      <Box sx={{ minWidth: 80 }}>
                        <LinearProgress />
                        <Typography variant="caption">Analisando fit</Typography>
                      </Box>
                    )}
                    {app.fit_status === 'analyzed' && app.fit_score != null && (
                      <Box textAlign="center">
                        <Typography variant="h6" fontWeight={700} lineHeight={1}>
                          {app.fit_score}
                        </Typography>
                        {app.fit_recommendation && (
                          <Chip
                            size="small"
                            label={RECOMMENDATION_LABELS[app.fit_recommendation]}
                            color={RECOMMENDATION_COLORS[app.fit_recommendation]}
                          />
                        )}
                      </Box>
                    )}
                  </Box>
                </Box>
                {app.fit_summary && (
                  <Typography variant="body2" color="text.secondary" mt={1}>
                    {app.fit_summary}
                  </Typography>
                )}
              </Box>
            ))
          )}
        </>
      )}

      <Dialog open={!!applyTarget} onClose={() => setApplyTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Aplicar para {applyTarget?.title}</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Sua candidatura sera enviada usando seu perfil atual. Voce pode adicionar
            uma mensagem opcional (carta de apresentacao).
          </Typography>
          <TextField
            label="Mensagem / carta de apresentacao"
            multiline
            minRows={3}
            fullWidth
            value={coverLetter}
            onChange={(e) => setCoverLetter(e.target.value)}
            sx={{ mt: 2 }}
          />
          <Divider sx={{ my: 2 }} />
          <Typography variant="caption" color="text.secondary">
            Ao aplicar, voce autoriza o compartilhamento dos seus dados com o RH
            da empresa para este processo seletivo.
          </Typography>
          {applying && <LinearProgress sx={{ mt: 2 }} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApplyTarget(null)} disabled={applying}>
            Cancelar
          </Button>
          <Button variant="contained" onClick={handleApply} disabled={applying}>
            Enviar candidatura
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default PortalJobsSection;
