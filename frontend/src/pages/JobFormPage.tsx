import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Grid,
  MenuItem,
  FormControlLabel,
  Switch,
  Chip,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import { ArrowBack, Save } from '@mui/icons-material';
import { apiService } from '../services/api';
import { JobCreate, Job } from '../types';
import { useNotification } from '../contexts/NotificationContext';

const EMPLOYMENT_TYPES = ['CLT', 'PJ', 'Estagio', 'Temporario', 'Freelance'];
const SENIORITY_LEVELS = ['Junior', 'Pleno', 'Senior', 'Especialista', 'Coordenador', 'Gerente'];
const WORK_MODES = ['presencial', 'remoto', 'hibrido'];

const JobFormPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showError, showSuccess } = useNotification();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<JobCreate>({
    title: '',
    description: '',
    requirements: '',
    responsibilities: '',
    benefits: '',
    location: '',
    employment_type: 'CLT',
    seniority_level: 'Pleno',
    work_mode: 'hibrido',
    salary_range_min: undefined,
    salary_range_max: undefined,
    salary_currency: 'BRL',
    salary_visible: false,
    skills_required: [],
    skills_desired: [],
    is_active: true,
  });
  const [skillInput, setSkillInput] = useState('');
  const [desiredSkillInput, setDesiredSkillInput] = useState('');

  useEffect(() => {
    if (isEdit && id) {
      loadJob(parseInt(id));
    }
  }, [id]);

  const loadJob = async (jobId: number) => {
    try {
      setLoading(true);
      const job: Job = await apiService.getJob(jobId);
      setForm({
        title: job.title,
        description: job.description,
        requirements: job.requirements || '',
        responsibilities: job.responsibilities || '',
        benefits: job.benefits || '',
        location: job.location || '',
        employment_type: job.employment_type || 'CLT',
        seniority_level: job.seniority_level || 'Pleno',
        work_mode: job.work_mode || 'hibrido',
        salary_range_min: job.salary_range_min,
        salary_range_max: job.salary_range_max,
        salary_currency: job.salary_currency || 'BRL',
        salary_visible: job.salary_visible || false,
        skills_required: job.skills_required || [],
        skills_desired: job.skills_desired || [],
        is_active: job.is_active,
      });
    } catch (err) {
      showError('Erro ao carregar vaga');
    } finally {
      setLoading(false);
    }
  };

  const addSkill = (key: 'skills_required' | 'skills_desired', value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    const arr = form[key] || [];
    if (arr.includes(trimmed)) return;
    setForm({ ...form, [key]: [...arr, trimmed] });
  };

  const removeSkill = (key: 'skills_required' | 'skills_desired', value: string) => {
    setForm({ ...form, [key]: (form[key] || []).filter((s) => s !== value) });
  };

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.description.trim()) {
      showError('Titulo e descricao sao obrigatorios');
      return;
    }
    try {
      setSaving(true);
      if (isEdit && id) {
        await apiService.updateJob(parseInt(id), form);
        showSuccess('Vaga atualizada');
      } else {
        const created = await apiService.createJob(form);
        showSuccess('Vaga criada');
        navigate(`/jobs/${created.id}`);
        return;
      }
      navigate('/jobs');
    } catch (err) {
      showError('Erro ao salvar vaga');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

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
            {isEdit ? 'Editar vaga' : 'Nova vaga'}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Save />}
          onClick={handleSubmit}
          disabled={saving}
        >
          {isEdit ? 'Salvar alteracoes' : 'Publicar vaga'}
        </Button>
      </Box>

      <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              label="Titulo da vaga"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              fullWidth
              required
              placeholder="Ex: Desenvolvedor Backend Python Senior"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Localizacao"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              fullWidth
              placeholder="Sao Paulo, SP"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Modo de trabalho"
              select
              value={form.work_mode}
              onChange={(e) => setForm({ ...form, work_mode: e.target.value })}
              fullWidth
            >
              {WORK_MODES.map((m) => (
                <MenuItem key={m} value={m}>
                  {m}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Tipo de contrato"
              select
              value={form.employment_type}
              onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
              fullWidth
            >
              {EMPLOYMENT_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Senioridade"
              select
              value={form.seniority_level}
              onChange={(e) => setForm({ ...form, seniority_level: e.target.value })}
              fullWidth
            >
              {SENIORITY_LEVELS.map((s) => (
                <MenuItem key={s} value={s}>
                  {s}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              label="Salario minimo"
              type="number"
              value={form.salary_range_min ?? ''}
              onChange={(e) =>
                setForm({ ...form, salary_range_min: e.target.value ? Number(e.target.value) : undefined })
              }
              fullWidth
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              label="Salario maximo"
              type="number"
              value={form.salary_range_max ?? ''}
              onChange={(e) =>
                setForm({ ...form, salary_range_max: e.target.value ? Number(e.target.value) : undefined })
              }
              fullWidth
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormControlLabel
              control={
                <Switch
                  checked={form.salary_visible}
                  onChange={(e) => setForm({ ...form, salary_visible: e.target.checked })}
                />
              }
              label="Mostrar salario publicamente"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              label="Descricao completa"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              multiline
              minRows={6}
              fullWidth
              required
              helperText="Sobre a vaga, contexto, missao. Pode usar markdown simples."
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label="Requisitos"
              value={form.requirements}
              onChange={(e) => setForm({ ...form, requirements: e.target.value })}
              multiline
              minRows={4}
              fullWidth
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label="Responsabilidades"
              value={form.responsibilities}
              onChange={(e) => setForm({ ...form, responsibilities: e.target.value })}
              multiline
              minRows={4}
              fullWidth
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label="Beneficios"
              value={form.benefits}
              onChange={(e) => setForm({ ...form, benefits: e.target.value })}
              multiline
              minRows={3}
              fullWidth
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Skills exigidas
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap" mb={1}>
              {(form.skills_required || []).map((s) => (
                <Chip key={s} label={s} onDelete={() => removeSkill('skills_required', s)} />
              ))}
            </Box>
            <TextField
              size="small"
              placeholder="Digite e pressione Enter"
              value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addSkill('skills_required', skillInput);
                  setSkillInput('');
                }
              }}
              fullWidth
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Skills desejaveis
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap" mb={1}>
              {(form.skills_desired || []).map((s) => (
                <Chip key={s} label={s} onDelete={() => removeSkill('skills_desired', s)} />
              ))}
            </Box>
            <TextField
              size="small"
              placeholder="Digite e pressione Enter"
              value={desiredSkillInput}
              onChange={(e) => setDesiredSkillInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addSkill('skills_desired', desiredSkillInput);
                  setDesiredSkillInput('');
                }
              }}
              fullWidth
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
              }
              label="Vaga ativa (visivel na pagina publica)"
            />
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default JobFormPage;
