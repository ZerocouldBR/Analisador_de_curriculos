import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Tooltip,
  TextField,
  InputAdornment,
  CircularProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  ContentCopy,
  Edit,
  OpenInNew,
  Work,
  Search,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Job } from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { useCompany } from '../contexts/CompanyContext';

const JobsPage: React.FC = () => {
  const navigate = useNavigate();
  const { showError, showSuccess } = useNotification();
  const { company } = useCompany();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const data = await apiService.listJobs(true);
      setJobs(data);
    } catch (err) {
      showError('Erro ao carregar vagas');
    } finally {
      setLoading(false);
    }
  };

  const copyPublicLink = (job: Job) => {
    if (!company?.slug) {
      showError('A empresa precisa ter um slug configurado');
      return;
    }
    const url = `${window.location.origin}/careers/${company.slug}/${job.slug}`;
    navigator.clipboard.writeText(url);
    showSuccess('Link publico copiado');
  };

  const filteredJobs = jobs.filter((j) =>
    j.title.toLowerCase().includes(filter.toLowerCase()) ||
    (j.location || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <Box className="fade-in">
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Vagas
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Gerencie vagas publicadas e aplicacoes recebidas
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          {company?.slug && (
            <Button
              variant="outlined"
              startIcon={<OpenInNew />}
              onClick={() => window.open(`/careers/${company.slug}`, '_blank')}
            >
              Ver pagina publica
            </Button>
          )}
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate('/jobs/new')}>
            Nova vaga
          </Button>
        </Box>
      </Box>

      <Box mb={2}>
        <TextField
          placeholder="Buscar por titulo ou localizacao"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          fullWidth
          size="small"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      <Paper sx={{ border: '1px solid', borderColor: 'divider' }}>
        {loading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : filteredJobs.length === 0 ? (
          <Box p={4} textAlign="center">
            <Work color="disabled" sx={{ fontSize: 48 }} />
            <Typography variant="h6" mt={1}>
              Nenhuma vaga ainda
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              Crie uma vaga para receber candidaturas pelo link publico
            </Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate('/jobs/new')}>
              Criar primeira vaga
            </Button>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Titulo</TableCell>
                  <TableCell>Localizacao</TableCell>
                  <TableCell>Senioridade</TableCell>
                  <TableCell>Modo</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="center">Aplicacoes</TableCell>
                  <TableCell align="right">Acoes</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredJobs.map((job) => (
                  <TableRow
                    key={job.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/jobs/${job.id}`)}
                  >
                    <TableCell>
                      <Typography fontWeight={500}>{job.title}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        /{job.slug}
                      </Typography>
                    </TableCell>
                    <TableCell>{job.location || '-'}</TableCell>
                    <TableCell>{job.seniority_level || '-'}</TableCell>
                    <TableCell>{job.work_mode || '-'}</TableCell>
                    <TableCell>
                      <Chip
                        label={job.is_active ? 'Ativa' : 'Inativa'}
                        color={job.is_active ? 'success' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip label={job.applications_count ?? 0} size="small" />
                    </TableCell>
                    <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                      <Tooltip title="Copiar link publico">
                        <IconButton size="small" onClick={() => copyPublicLink(job)}>
                          <ContentCopy fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Editar">
                        <IconButton size="small" onClick={() => navigate(`/jobs/${job.id}/edit`)}>
                          <Edit fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
};

export default JobsPage;
