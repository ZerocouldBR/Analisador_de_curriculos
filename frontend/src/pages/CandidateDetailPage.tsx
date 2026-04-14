import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Button,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  IconButton,
  Tooltip,
  Tab,
  Tabs,
  useTheme,
  alpha,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Link,
} from '@mui/material';
import {
  ArrowBack,
  Email,
  Phone,
  LocationOn,
  Description,
  Work,
  Refresh,
  CalendarToday,
  Badge,
  CloudUpload,
  SmartToy,
  Hub,
  OpenInNew,
  Timeline,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Candidate, Document, Experience, CandidateSource } from '../types';
import { DetailSkeleton } from '../components/LoadingSkeleton';
import { useNotification } from '../contexts/NotificationContext';

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div hidden={value !== index}>{value === index && <Box sx={{ py: 2 }}>{children}</Box>}</div>
);

const CandidateDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const { showError, showSuccess } = useNotification();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [sources, setSources] = useState<CandidateSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);

  useEffect(() => {
    if (id) fetchData();
  }, [id]);

  const fetchData = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const candidateId = parseInt(id);
      const [candidateData, documentsData] = await Promise.all([
        apiService.getCandidate(candidateId),
        apiService.getCandidateDocuments(candidateId),
      ]);
      setCandidate(candidateData);
      setDocuments(documentsData);

      try {
        const experiencesData = await apiService.getCandidateExperiences(candidateId);
        setExperiences(experiencesData);
      } catch {
        // Experiences endpoint might not exist yet
      }

      try {
        const sourcesResponse = await apiService.getCandidateSources(candidateId);
        setSources(sourcesResponse.data);
      } catch {
        // Sources endpoint might not exist yet
      }
    } catch (error) {
      showError('Erro ao carregar dados do candidato');
    } finally {
      setLoading(false);
    }
  };

  const handleReprocess = async (docId: number) => {
    try {
      await apiService.reprocessDocument(docId);
      showSuccess('Documento enviado para reprocessamento');
    } catch (error) {
      showError('Erro ao reprocessar documento');
    }
  };

  if (loading) return <DetailSkeleton />;

  if (!candidate) {
    return (
      <Box textAlign="center" py={8}>
        <Typography variant="h5" gutterBottom>Candidato nao encontrado</Typography>
        <Button variant="contained" onClick={() => navigate('/candidates')}>
          Voltar para lista
        </Button>
      </Box>
    );
  }

  const InfoItem = ({ icon, label, value }: { icon: React.ReactElement; label: string; value: string }) => (
    <Box display="flex" alignItems="center" gap={1.5} py={1}>
      <Box
        sx={{
          p: 1,
          borderRadius: 1.5,
          bgcolor: alpha(theme.palette.primary.main, 0.08),
          display: 'flex',
        }}
      >
        {React.cloneElement(icon, { fontSize: 'small', color: 'primary' })}
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="body2" fontWeight={500}>
          {value || 'Nao informado'}
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Tooltip title="Voltar">
          <IconButton onClick={() => navigate('/candidates')}>
            <ArrowBack />
          </IconButton>
        </Tooltip>
        <Box flexGrow={1}>
          <Typography variant="h4" fontWeight={700}>
            {candidate.full_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Cadastrado em {new Date(candidate.created_at).toLocaleDateString('pt-BR')}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<SmartToy />}
          onClick={() => navigate('/chat')}
        >
          Analisar com IA
        </Button>
      </Box>

      <Grid container spacing={3}>
        {/* Left column - Info */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ border: '1px solid', borderColor: 'divider', mb: 3 }}>
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Tab label="Informacoes" />
              <Tab label={`Documentos (${documents.length})`} />
              <Tab label={`Experiencias (${experiences.length})`} />
              <Tab label={`Fontes (${sources.length})`} />
            </Tabs>

            <TabPanel value={tab} index={0}>
              <Box sx={{ px: 3 }}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <InfoItem icon={<Email />} label="Email" value={candidate.email || ''} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <InfoItem icon={<Phone />} label="Telefone" value={candidate.phone || ''} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <InfoItem
                      icon={<LocationOn />}
                      label="Localizacao"
                      value={
                        candidate.city && candidate.state
                          ? `${candidate.city}, ${candidate.state}`
                          : candidate.city || candidate.state || ''
                      }
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <InfoItem
                      icon={<Badge />}
                      label="CPF"
                      value={
                        candidate.doc_id
                          ? candidate.doc_id.replace(/^(\d{3})\d{3}\d{3}(\d{2})$/, '$1.***.***-$2')
                          : ''
                      }
                    />
                  </Grid>
                  {candidate.address && (
                    <Grid item xs={12}>
                      <InfoItem icon={<LocationOn />} label="Endereco" value={candidate.address} />
                    </Grid>
                  )}
                  {candidate.birth_date && (
                    <Grid item xs={12} sm={6}>
                      <InfoItem
                        icon={<CalendarToday />}
                        label="Data de Nascimento"
                        value={new Date(candidate.birth_date).toLocaleDateString('pt-BR')}
                      />
                    </Grid>
                  )}
                </Grid>
              </Box>
            </TabPanel>

            <TabPanel value={tab} index={1}>
              <Box sx={{ px: 3 }}>
                {documents.length === 0 ? (
                  <Box textAlign="center" py={4}>
                    <Description sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography color="text.secondary">Nenhum documento enviado</Typography>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<CloudUpload />}
                      sx={{ mt: 2 }}
                      onClick={() => navigate('/upload')}
                    >
                      Fazer Upload
                    </Button>
                  </Box>
                ) : (
                  <List disablePadding>
                    {documents.map((doc, i) => (
                      <React.Fragment key={doc.id}>
                        {i > 0 && <Divider />}
                        <ListItem
                          sx={{ px: 0 }}
                          secondaryAction={
                            <Tooltip title="Reprocessar">
                              <IconButton size="small" onClick={() => handleReprocess(doc.id)}>
                                <Refresh fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          }
                        >
                          <ListItemIcon>
                            <Description color="primary" />
                          </ListItemIcon>
                          <ListItemText
                            primary={
                              <Typography variant="body2" fontWeight={500}>
                                {doc.original_filename}
                              </Typography>
                            }
                            secondary={
                              <Box display="flex" gap={1} alignItems="center" mt={0.5}>
                                <Chip label={doc.mime_type} size="small" variant="outlined" />
                                <Typography variant="caption" color="text.secondary">
                                  {new Date(doc.uploaded_at).toLocaleString('pt-BR')}
                                </Typography>
                              </Box>
                            }
                          />
                        </ListItem>
                      </React.Fragment>
                    ))}
                  </List>
                )}
              </Box>
            </TabPanel>

            <TabPanel value={tab} index={2}>
              <Box sx={{ px: 3 }}>
                {experiences.length === 0 ? (
                  <Box textAlign="center" py={4}>
                    <Work sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography color="text.secondary">
                      Nenhuma experiencia registrada
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      As experiencias sao extraidas automaticamente dos curriculos
                    </Typography>
                  </Box>
                ) : (
                  experiences.map((exp, i) => (
                    <Box
                      key={exp.id}
                      sx={{
                        py: 2,
                        borderLeft: '3px solid',
                        borderColor: 'primary.main',
                        pl: 2,
                        mb: 2,
                      }}
                    >
                      <Typography variant="subtitle2" fontWeight={600}>
                        {exp.role_title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {exp.company_name}
                        {exp.location ? ` - ${exp.location}` : ''}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {exp.start_date || '?'} - {exp.is_current ? 'Atual' : exp.end_date || '?'}
                      </Typography>
                      {exp.description && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          {exp.description}
                        </Typography>
                      )}
                    </Box>
                  ))
                )}
              </Box>
            </TabPanel>

            <TabPanel value={tab} index={3}>
              <Box sx={{ px: 3 }}>
                {sources.length === 0 ? (
                  <Box textAlign="center" py={4}>
                    <Hub sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography color="text.secondary">
                      Nenhuma fonte de sourcing vinculada
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Fontes sao criadas automaticamente durante sincronizacoes
                    </Typography>
                  </Box>
                ) : (
                  <>
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Provider</TableCell>
                            <TableCell>Tipo</TableCell>
                            <TableCell>URL Externa</TableCell>
                            <TableCell>Confianca</TableCell>
                            <TableCell>Ultimo Sync</TableCell>
                            <TableCell>Status</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {sources.map((source) => (
                            <TableRow key={source.id}>
                              <TableCell>
                                <Typography variant="body2" fontWeight={500}>
                                  {source.provider_name}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Chip label={source.provider_type} size="small" variant="outlined" />
                              </TableCell>
                              <TableCell>
                                {source.external_url ? (
                                  <Link
                                    href={source.external_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                                  >
                                    <Typography variant="body2" noWrap sx={{ maxWidth: 150 }}>
                                      {source.external_url}
                                    </Typography>
                                    <OpenInNew sx={{ fontSize: 14 }} />
                                  </Link>
                                ) : (
                                  <Typography variant="body2" color="text.secondary">-</Typography>
                                )}
                              </TableCell>
                              <TableCell>
                                <Box display="flex" alignItems="center" gap={1} minWidth={100}>
                                  <LinearProgress
                                    variant="determinate"
                                    value={source.source_confidence * 100}
                                    sx={{ flex: 1, height: 6, borderRadius: 3 }}
                                  />
                                  <Typography variant="caption" fontWeight={500}>
                                    {Math.round(source.source_confidence * 100)}%
                                  </Typography>
                                </Box>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  {source.last_sync_at
                                    ? new Date(source.last_sync_at).toLocaleString('pt-BR')
                                    : 'Nunca'}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Chip
                                  label={source.last_status || 'N/A'}
                                  size="small"
                                  color={
                                    source.last_status === 'success'
                                      ? 'success'
                                      : source.last_status === 'error'
                                      ? 'error'
                                      : 'default'
                                  }
                                  variant="outlined"
                                />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    <Box display="flex" justifyContent="flex-end" mt={2}>
                      <Button
                        variant="outlined"
                        startIcon={<Timeline />}
                        onClick={() => navigate(`/candidates/${id}/snapshots`)}
                      >
                        Ver Snapshots
                      </Button>
                    </Box>
                  </>
                )}
              </Box>
            </TabPanel>
          </Paper>
        </Grid>

        {/* Right column - Stats */}
        <Grid item xs={12} md={4}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Resumo
              </Typography>
              <Box sx={{ mt: 2 }}>
                <Box display="flex" justifyContent="space-between" py={1}>
                  <Typography variant="body2" color="text.secondary">Documentos</Typography>
                  <Typography variant="body2" fontWeight={600}>{documents.length}</Typography>
                </Box>
                <Divider />
                <Box display="flex" justifyContent="space-between" py={1}>
                  <Typography variant="body2" color="text.secondary">Experiencias</Typography>
                  <Typography variant="body2" fontWeight={600}>{experiences.length}</Typography>
                </Box>
                <Divider />
                <Box display="flex" justifyContent="space-between" py={1}>
                  <Typography variant="body2" color="text.secondary">Cadastro</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {new Date(candidate.created_at).toLocaleDateString('pt-BR')}
                  </Typography>
                </Box>
                <Divider />
                <Box display="flex" justifyContent="space-between" py={1}>
                  <Typography variant="body2" color="text.secondary">Atualizado</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {new Date(candidate.updated_at).toLocaleDateString('pt-BR')}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {candidate.city && (
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Localizacao
                </Typography>
                <Chip
                  icon={<LocationOn />}
                  label={`${candidate.city}${candidate.state ? ', ' + candidate.state : ''}`}
                  color="primary"
                  variant="outlined"
                />
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default CandidateDetailPage;
