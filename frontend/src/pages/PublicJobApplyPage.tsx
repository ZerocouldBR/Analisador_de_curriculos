import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Container,
  Paper,
  Button,
  Chip,
  TextField,
  Grid,
  Divider,
  Avatar,
  CircularProgress,
  Alert,
  AlertTitle,
  FormControlLabel,
  Checkbox,
  ThemeProvider,
  createTheme,
  LinearProgress,
} from '@mui/material';
import { ArrowBack, CloudUpload, CheckCircle } from '@mui/icons-material';
import { apiService } from '../services/api';
import { PublicJobResponse, ApplyResult } from '../types';

const PublicJobApplyPage: React.FC = () => {
  const { companySlug, jobSlug } = useParams<{ companySlug: string; jobSlug: string }>();
  const navigate = useNavigate();

  const [job, setJob] = useState<PublicJobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ApplyResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    applicant_name: '',
    applicant_email: '',
    applicant_phone: '',
    cover_letter: '',
    consent_given: false,
  });
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    if (!companySlug || !jobSlug) return;
    apiService
      .getPublicJob(companySlug, jobSlug)
      .then((j) => setJob(j))
      .catch(() => setError('Vaga nao encontrada ou indisponivel'))
      .finally(() => setLoading(false));
  }, [companySlug, jobSlug]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companySlug || !jobSlug) return;
    if (!file) {
      setError('Anexe seu curriculo');
      return;
    }
    if (!form.consent_given) {
      setError('Voce precisa autorizar o tratamento dos dados');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const res = await apiService.applyToPublicJob(companySlug, jobSlug, {
        resume: file,
        ...form,
      });
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao enviar candidatura');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!job) {
    return (
      <Container maxWidth="md" sx={{ py: 8 }}>
        <Typography variant="h4">Vaga nao encontrada</Typography>
        <Typography color="text.secondary">{error}</Typography>
      </Container>
    );
  }

  const brand = job.company;
  const brandColor = brand.brand_color || '#1976d2';
  const pageTheme = createTheme({ palette: { primary: { main: brandColor } } });

  if (result) {
    return (
      <ThemeProvider theme={pageTheme}>
        <Container maxWidth="sm" sx={{ py: 8 }}>
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <CheckCircle sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
            <Typography variant="h5" gutterBottom>
              Candidatura recebida
            </Typography>
            <Typography color="text.secondary" paragraph>
              {result.message}
            </Typography>
            <Button
              variant="contained"
              onClick={() => navigate(`/careers/${companySlug}`)}
            >
              Ver outras vagas
            </Button>
          </Paper>
        </Container>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={pageTheme}>
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
        <Box sx={{ bgcolor: brandColor, color: '#fff', py: 3 }}>
          <Container maxWidth="lg">
            <Box display="flex" alignItems="center" gap={2}>
              <Button
                startIcon={<ArrowBack />}
                onClick={() => navigate(`/careers/${companySlug}`)}
                sx={{ color: '#fff' }}
              >
                Voltar
              </Button>
              {brand.logo_url && (
                <Avatar
                  src={brand.logo_url.startsWith('http') ? brand.logo_url : undefined}
                  sx={{ bgcolor: 'rgba(255,255,255,0.2)' }}
                />
              )}
              <Typography variant="h6">{brand.name}</Typography>
            </Box>
          </Container>
        </Box>

        <Container maxWidth="lg" sx={{ py: 4 }}>
          <Grid container spacing={4}>
            <Grid item xs={12} md={7}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h4" fontWeight={700} gutterBottom>
                  {job.title}
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={1} mb={2}>
                  {job.location && <Chip size="small" label={job.location} />}
                  {job.work_mode && <Chip size="small" label={job.work_mode} variant="outlined" />}
                  {job.employment_type && (
                    <Chip size="small" label={job.employment_type} variant="outlined" />
                  )}
                  {job.seniority_level && (
                    <Chip size="small" label={job.seniority_level} variant="outlined" />
                  )}
                </Box>
                {job.salary_display && (
                  <Typography variant="h6" color="primary" gutterBottom>
                    {job.salary_display}
                  </Typography>
                )}
                <Divider sx={{ my: 2 }} />

                <Typography variant="subtitle2" gutterBottom>
                  Descricao
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }} paragraph>
                  {job.description}
                </Typography>

                {job.responsibilities && (
                  <>
                    <Typography variant="subtitle2" gutterBottom>
                      Responsabilidades
                    </Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }} paragraph>
                      {job.responsibilities}
                    </Typography>
                  </>
                )}

                {job.requirements && (
                  <>
                    <Typography variant="subtitle2" gutterBottom>
                      Requisitos
                    </Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }} paragraph>
                      {job.requirements}
                    </Typography>
                  </>
                )}

                {job.benefits && (
                  <>
                    <Typography variant="subtitle2" gutterBottom>
                      Beneficios
                    </Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }} paragraph>
                      {job.benefits}
                    </Typography>
                  </>
                )}

                {(job.skills_required?.length || 0) > 0 && (
                  <Box mt={2}>
                    <Typography variant="subtitle2" gutterBottom>
                      Skills exigidas
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap">
                      {job.skills_required.map((s) => (
                        <Chip key={s} label={s} size="small" color="primary" />
                      ))}
                    </Box>
                  </Box>
                )}

                {(job.skills_desired?.length || 0) > 0 && (
                  <Box mt={2}>
                    <Typography variant="subtitle2" gutterBottom>
                      Desejaveis
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap">
                      {job.skills_desired.map((s) => (
                        <Chip key={s} label={s} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Box>
                )}
              </Paper>
            </Grid>

            <Grid item xs={12} md={5}>
              <Paper sx={{ p: 3, position: 'sticky', top: 16 }}>
                <Typography variant="h6" gutterBottom>
                  Candidatar-se
                </Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Envie seu curriculo e nossa IA analisa automaticamente o quanto
                  seu perfil se encaixa na vaga.
                </Typography>
                <Divider sx={{ my: 2 }} />

                {error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    <AlertTitle>Erro</AlertTitle>
                    {error}
                  </Alert>
                )}

                <form onSubmit={handleSubmit}>
                  <TextField
                    label="Nome completo"
                    required
                    fullWidth
                    margin="normal"
                    value={form.applicant_name}
                    onChange={(e) => setForm({ ...form, applicant_name: e.target.value })}
                  />
                  <TextField
                    label="Email"
                    type="email"
                    required
                    fullWidth
                    margin="normal"
                    value={form.applicant_email}
                    onChange={(e) => setForm({ ...form, applicant_email: e.target.value })}
                  />
                  <TextField
                    label="Telefone"
                    fullWidth
                    margin="normal"
                    value={form.applicant_phone}
                    onChange={(e) => setForm({ ...form, applicant_phone: e.target.value })}
                  />
                  <TextField
                    label="Mensagem / carta de apresentacao"
                    fullWidth
                    multiline
                    minRows={3}
                    margin="normal"
                    value={form.cover_letter}
                    onChange={(e) => setForm({ ...form, cover_letter: e.target.value })}
                  />

                  <Box mt={2}>
                    <Button
                      component="label"
                      variant="outlined"
                      fullWidth
                      startIcon={<CloudUpload />}
                    >
                      {file ? file.name : 'Anexar curriculo (PDF, DOCX)'}
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,.txt,.rtf"
                        hidden
                        onChange={handleFileChange}
                      />
                    </Button>
                  </Box>

                  <FormControlLabel
                    sx={{ mt: 2 }}
                    control={
                      <Checkbox
                        checked={form.consent_given}
                        onChange={(e) =>
                          setForm({ ...form, consent_given: e.target.checked })
                        }
                      />
                    }
                    label={
                      <Typography variant="caption">
                        Autorizo {brand.name} a processar meus dados para fins de
                        recrutamento, conforme a LGPD.
                      </Typography>
                    }
                  />

                  {submitting && <LinearProgress sx={{ mt: 2 }} />}

                  <Button
                    type="submit"
                    variant="contained"
                    fullWidth
                    sx={{ mt: 2 }}
                    disabled={submitting}
                  >
                    {submitting ? 'Enviando...' : 'Enviar candidatura'}
                  </Button>
                </form>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>
    </ThemeProvider>
  );
};

export default PublicJobApplyPage;
