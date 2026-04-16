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
  Alert,
  AlertTitle,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
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
  School,
  Star,
  Language,
  VerifiedUser,
  TipsAndUpdates,
  ExpandMore,
  Warning,
  CheckCircle,
  Error as ErrorIcon,
  LinkedIn,
  GitHub,
  Link as LinkIcon,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import {
  Candidate,
  Document,
  Experience,
  CandidateSource,
  EnrichedResumeProfile,
  CareerAdvisoryResponse,
} from '../types';
import { DetailSkeleton } from '../components/LoadingSkeleton';
import CandidateAccessTokenDialog from '../components/CandidateAccessTokenDialog';
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
  const [enrichedProfile, setEnrichedProfile] = useState<EnrichedResumeProfile | null>(null);
  const [careerAdvisory, setCareerAdvisory] = useState<CareerAdvisoryResponse | null>(null);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [tokenDialogOpen, setTokenDialogOpen] = useState(false);

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
      } catch (err) {
        console.warn('Failed to fetch candidate experiences:', err);
      }

      try {
        const sourcesData = await apiService.getCandidateSources(candidateId);
        setSources(sourcesData);
      } catch (err) {
        console.warn('Failed to fetch candidate sources:', err);
      }

      try {
        const enrichedData = await apiService.getEnrichedProfile(candidateId);
        setEnrichedProfile(enrichedData);
      } catch (err) {
        console.warn('Failed to fetch enriched profile:', err);
      }
    } catch (error) {
      showError('Erro ao carregar dados do candidato');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestAdvisory = async () => {
    if (!id) return;
    setAdvisoryLoading(true);
    try {
      const result = await apiService.getCareerAdvisory(parseInt(id));
      setCareerAdvisory(result);
      if (result.available) {
        showSuccess('Consultoria de carreira gerada com sucesso');
      }
    } catch (error) {
      showError('Erro ao gerar consultoria de carreira');
    } finally {
      setAdvisoryLoading(false);
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
          startIcon={<LinkIcon />}
          onClick={() => setTokenDialogOpen(true)}
          sx={{ mr: 1 }}
        >
          Link do candidato
        </Button>
        <Button
          variant="outlined"
          startIcon={<SmartToy />}
          onClick={() => navigate('/chat')}
        >
          Analisar com IA
        </Button>
      </Box>

      {candidate && (
        <CandidateAccessTokenDialog
          candidateId={candidate.id}
          open={tokenDialogOpen}
          onClose={() => setTokenDialogOpen(false)}
        />
      )}

      <Grid container spacing={3}>
        {/* Left column - Info */}
        <Grid item xs={12} md={8}>
          {/* Validation Alerts */}
          {enrichedProfile?.validation?.alerts && enrichedProfile.validation.alerts.length > 0 && (
            <Box mb={2}>
              {enrichedProfile.validation.alerts
                .filter((a) => a.severity === 'critical' || a.severity === 'high')
                .map((alert, i) => (
                  <Alert
                    key={i}
                    severity={alert.severity === 'critical' ? 'error' : 'warning'}
                    sx={{ mb: 1 }}
                    icon={alert.severity === 'critical' ? <ErrorIcon /> : <Warning />}
                  >
                    <AlertTitle>{alert.field}: {alert.type}</AlertTitle>
                    {alert.message}
                    {alert.suggestion && (
                      <Typography variant="caption" display="block" mt={0.5}>
                        Sugestao: {alert.suggestion}
                      </Typography>
                    )}
                  </Alert>
                ))}
            </Box>
          )}

          <Paper sx={{ border: '1px solid', borderColor: 'divider', mb: 3 }}>
            <Tabs
              value={tab}
              onChange={(_, v) => setTab(v)}
              variant="scrollable"
              scrollButtons="auto"
              sx={{ px: 2, borderBottom: '1px solid', borderColor: 'divider' }}
            >
              <Tab label="Informacoes" />
              <Tab label={`Documentos (${documents.length})`} />
              <Tab label={`Experiencias (${experiences.length})`} />
              <Tab label="Skills" />
              <Tab label="Formacao" />
              <Tab label="Consultoria" />
              <Tab label={`Fontes (${sources.length})`} />
            </Tabs>

            <TabPanel value={tab} index={0}>
              <Box sx={{ px: 3 }}>
                {/* Professional Objective */}
                {enrichedProfile?.professional_objective?.summary && (
                  <Box mb={3} p={2} bgcolor={alpha(theme.palette.primary.main, 0.04)} borderRadius={2}>
                    {enrichedProfile.professional_objective.title && (
                      <Typography variant="subtitle2" color="primary" gutterBottom>
                        {enrichedProfile.professional_objective.title}
                      </Typography>
                    )}
                    <Typography variant="body2" color="text.secondary">
                      {enrichedProfile.professional_objective.summary}
                    </Typography>
                  </Box>
                )}

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
                  {enrichedProfile?.personal_info?.full_address && (
                    <Grid item xs={12}>
                      <InfoItem icon={<LocationOn />} label="Endereco Completo" value={enrichedProfile.personal_info.full_address} />
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
                  {enrichedProfile?.personal_info?.linkedin && (
                    <Grid item xs={12} sm={6}>
                      <Box display="flex" alignItems="center" gap={1.5} py={1}>
                        <Box sx={{ p: 1, borderRadius: 1.5, bgcolor: alpha(theme.palette.primary.main, 0.08), display: 'flex' }}>
                          <LinkedIn fontSize="small" color="primary" />
                        </Box>
                        <Box>
                          <Typography variant="caption" color="text.secondary">LinkedIn</Typography>
                          <Link href={enrichedProfile.personal_info.linkedin} target="_blank" rel="noopener">
                            <Typography variant="body2" fontWeight={500}>
                              {enrichedProfile.personal_info.linkedin.replace('https://linkedin.com/in/', '').replace('https://www.linkedin.com/in/', '')}
                            </Typography>
                          </Link>
                        </Box>
                      </Box>
                    </Grid>
                  )}
                  {enrichedProfile?.personal_info?.github && (
                    <Grid item xs={12} sm={6}>
                      <Box display="flex" alignItems="center" gap={1.5} py={1}>
                        <Box sx={{ p: 1, borderRadius: 1.5, bgcolor: alpha(theme.palette.primary.main, 0.08), display: 'flex' }}>
                          <GitHub fontSize="small" color="primary" />
                        </Box>
                        <Box>
                          <Typography variant="caption" color="text.secondary">GitHub</Typography>
                          <Link href={enrichedProfile.personal_info.github} target="_blank" rel="noopener">
                            <Typography variant="body2" fontWeight={500}>
                              {enrichedProfile.personal_info.github.replace('https://github.com/', '')}
                            </Typography>
                          </Link>
                        </Box>
                      </Box>
                    </Grid>
                  )}
                </Grid>

                {/* Languages */}
                {enrichedProfile?.languages && enrichedProfile.languages.length > 0 && (
                  <Box mt={3}>
                    <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                      <Language sx={{ fontSize: 18, mr: 0.5, verticalAlign: 'text-bottom' }} />
                      Idiomas
                    </Typography>
                    <Box display="flex" gap={1} flexWrap="wrap">
                      {enrichedProfile.languages.map((lang, i) => (
                        <Chip
                          key={i}
                          label={`${lang.language} - ${lang.level}`}
                          size="small"
                          variant="outlined"
                          color="primary"
                        />
                      ))}
                    </Box>
                  </Box>
                )}
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

            {/* Skills Tab */}
            <TabPanel value={tab} index={3}>
              <Box sx={{ px: 3 }}>
                {enrichedProfile?.skills ? (
                  <Grid container spacing={3}>
                    {enrichedProfile.skills.technical && enrichedProfile.skills.technical.length > 0 && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom color="primary">
                          Competencias Tecnicas
                        </Typography>
                        <Box display="flex" gap={0.5} flexWrap="wrap">
                          {enrichedProfile.skills.technical.map((skill, i) => (
                            <Chip key={i} label={skill} size="small" color="primary" variant="outlined" />
                          ))}
                        </Box>
                      </Grid>
                    )}
                    {enrichedProfile.skills.soft && enrichedProfile.skills.soft.length > 0 && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom sx={{ color: 'success.main' }}>
                          Competencias Comportamentais
                        </Typography>
                        <Box display="flex" gap={0.5} flexWrap="wrap">
                          {enrichedProfile.skills.soft.map((skill, i) => (
                            <Chip key={i} label={skill} size="small" color="success" variant="outlined" />
                          ))}
                        </Box>
                      </Grid>
                    )}
                    {enrichedProfile.skills.tools && enrichedProfile.skills.tools.length > 0 && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom sx={{ color: 'warning.main' }}>
                          Ferramentas
                        </Typography>
                        <Box display="flex" gap={0.5} flexWrap="wrap">
                          {enrichedProfile.skills.tools.map((tool, i) => (
                            <Chip key={i} label={tool} size="small" color="warning" variant="outlined" />
                          ))}
                        </Box>
                      </Grid>
                    )}
                    {enrichedProfile.skills.frameworks && enrichedProfile.skills.frameworks.length > 0 && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom sx={{ color: 'info.main' }}>
                          Frameworks
                        </Typography>
                        <Box display="flex" gap={0.5} flexWrap="wrap">
                          {enrichedProfile.skills.frameworks.map((fw, i) => (
                            <Chip key={i} label={fw} size="small" color="info" variant="outlined" />
                          ))}
                        </Box>
                      </Grid>
                    )}
                    {/* Certifications in skills tab */}
                    {enrichedProfile.certifications && enrichedProfile.certifications.length > 0 && (
                      <Grid item xs={12}>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                          <VerifiedUser sx={{ fontSize: 18, mr: 0.5, verticalAlign: 'text-bottom' }} />
                          Certificacoes
                        </Typography>
                        <Box display="flex" gap={0.5} flexWrap="wrap">
                          {enrichedProfile.certifications.map((cert, i) => (
                            <Chip
                              key={i}
                              label={cert.name || String(cert)}
                              size="small"
                              variant="outlined"
                              icon={<VerifiedUser />}
                            />
                          ))}
                        </Box>
                      </Grid>
                    )}
                    {/* Licenses */}
                    {enrichedProfile.licenses && enrichedProfile.licenses.length > 0 && (
                      <Grid item xs={12}>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                          Habilitacoes e Licencas
                        </Typography>
                        <Box display="flex" gap={0.5} flexWrap="wrap">
                          {enrichedProfile.licenses.map((lic, i) => (
                            <Chip
                              key={i}
                              label={`${lic.type}${lic.category ? ' - ' + lic.category : ''}`}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                        </Box>
                      </Grid>
                    )}
                  </Grid>
                ) : (
                  <Box textAlign="center" py={4}>
                    <Star sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography color="text.secondary">
                      Dados de skills nao disponiveis
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Reprocesse o documento para extrair skills enriquecidas
                    </Typography>
                  </Box>
                )}
              </Box>
            </TabPanel>

            {/* Education Tab */}
            <TabPanel value={tab} index={4}>
              <Box sx={{ px: 3 }}>
                {enrichedProfile?.education && enrichedProfile.education.length > 0 ? (
                  enrichedProfile.education.map((edu, i) => (
                    <Box
                      key={i}
                      sx={{
                        py: 2,
                        borderLeft: '3px solid',
                        borderColor: 'secondary.main',
                        pl: 2,
                        mb: 2,
                      }}
                    >
                      <Typography variant="subtitle2" fontWeight={600}>
                        {edu.degree || 'Curso'}
                      </Typography>
                      {edu.field && (
                        <Typography variant="body2" color="primary">
                          {edu.field}
                        </Typography>
                      )}
                      <Typography variant="body2" color="text.secondary">
                        {edu.institution || 'Instituicao nao informada'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {edu.start_year || '?'} - {edu.end_year || '?'}
                        {edu.status && ` (${edu.status})`}
                      </Typography>
                    </Box>
                  ))
                ) : (
                  <Box textAlign="center" py={4}>
                    <School sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography color="text.secondary">
                      Nenhuma formacao registrada
                    </Typography>
                  </Box>
                )}
              </Box>
            </TabPanel>

            {/* Career Advisory Tab */}
            <TabPanel value={tab} index={5}>
              <Box sx={{ px: 3 }}>
                {!careerAdvisory ? (
                  <Box textAlign="center" py={4}>
                    <TipsAndUpdates sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography color="text.secondary" gutterBottom>
                      Modulo de consultoria de carreira
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" mb={2}>
                      Gera analise completa do curriculo com sugestoes de melhoria, pontos fortes/fracos e recomendacoes.
                    </Typography>
                    <Button
                      variant="contained"
                      startIcon={advisoryLoading ? <CircularProgress size={16} /> : <TipsAndUpdates />}
                      onClick={handleRequestAdvisory}
                      disabled={advisoryLoading}
                    >
                      {advisoryLoading ? 'Gerando analise...' : 'Gerar Consultoria'}
                    </Button>
                  </Box>
                ) : careerAdvisory.available && careerAdvisory.advisory ? (
                  <Box>
                    {/* Score */}
                    {careerAdvisory.advisory.overall_score != null && (
                      <Box mb={3} display="flex" alignItems="center" gap={2}>
                        <Box
                          sx={{
                            width: 80,
                            height: 80,
                            borderRadius: '50%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            bgcolor: careerAdvisory.advisory.overall_score >= 70 ? 'success.light' : careerAdvisory.advisory.overall_score >= 40 ? 'warning.light' : 'error.light',
                          }}
                        >
                          <Typography variant="h4" fontWeight={700}>
                            {careerAdvisory.advisory.overall_score}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="h6" fontWeight={600}>Pontuacao Geral</Typography>
                          <Typography variant="body2" color="text.secondary">
                            Avaliacao de qualidade do curriculo
                          </Typography>
                        </Box>
                      </Box>
                    )}

                    {/* Suggested Summary */}
                    {careerAdvisory.advisory.suggested_summary && (
                      <Alert severity="info" sx={{ mb: 2 }}>
                        <AlertTitle>Resumo Profissional Sugerido</AlertTitle>
                        {careerAdvisory.advisory.suggested_summary}
                      </Alert>
                    )}

                    {/* Strengths */}
                    {careerAdvisory.advisory.strengths && careerAdvisory.advisory.strengths.length > 0 && (
                      <Accordion defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMore />}>
                          <CheckCircle color="success" sx={{ mr: 1 }} />
                          <Typography fontWeight={600}>Pontos Fortes</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          {careerAdvisory.advisory.strengths.map((s, i) => (
                            <Box key={i} display="flex" alignItems="center" gap={1} mb={1}>
                              <Chip label={s.impact} size="small" color="success" variant="outlined" />
                              <Typography variant="body2">{s.point}</Typography>
                            </Box>
                          ))}
                        </AccordionDetails>
                      </Accordion>
                    )}

                    {/* Weaknesses */}
                    {careerAdvisory.advisory.weaknesses && careerAdvisory.advisory.weaknesses.length > 0 && (
                      <Accordion defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMore />}>
                          <Warning color="warning" sx={{ mr: 1 }} />
                          <Typography fontWeight={600}>Pontos a Melhorar</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          {careerAdvisory.advisory.weaknesses.map((w, i) => (
                            <Box key={i} mb={2}>
                              <Box display="flex" alignItems="center" gap={1}>
                                <Chip label={w.priority} size="small" color="warning" variant="outlined" />
                                <Typography variant="body2" fontWeight={500}>{w.point}</Typography>
                              </Box>
                              <Typography variant="caption" color="text.secondary" sx={{ ml: 4 }}>
                                Sugestao: {w.suggestion}
                              </Typography>
                            </Box>
                          ))}
                        </AccordionDetails>
                      </Accordion>
                    )}

                    {/* Suggested Keywords */}
                    {careerAdvisory.advisory.suggested_keywords && careerAdvisory.advisory.suggested_keywords.length > 0 && (
                      <Accordion>
                        <AccordionSummary expandIcon={<ExpandMore />}>
                          <Typography fontWeight={600}>Palavras-Chave Sugeridas</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          <Box display="flex" gap={0.5} flexWrap="wrap">
                            {careerAdvisory.advisory.suggested_keywords.map((kw, i) => (
                              <Chip key={i} label={kw} size="small" color="primary" variant="outlined" />
                            ))}
                          </Box>
                        </AccordionDetails>
                      </Accordion>
                    )}

                    {/* HR Recommendations */}
                    {careerAdvisory.advisory.hr_recommendations && careerAdvisory.advisory.hr_recommendations.length > 0 && (
                      <Accordion>
                        <AccordionSummary expandIcon={<ExpandMore />}>
                          <Typography fontWeight={600}>Recomendacoes para RH</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          {careerAdvisory.advisory.hr_recommendations.map((r, i) => (
                            <Box key={i} mb={1}>
                              <Typography variant="body2" fontWeight={500}>{r.recommendation}</Typography>
                              <Typography variant="caption" color="text.secondary">{r.context}</Typography>
                            </Box>
                          ))}
                        </AccordionDetails>
                      </Accordion>
                    )}

                    {/* Suitable Areas */}
                    {careerAdvisory.advisory.suitable_areas && careerAdvisory.advisory.suitable_areas.length > 0 && (
                      <Accordion>
                        <AccordionSummary expandIcon={<ExpandMore />}>
                          <Typography fontWeight={600}>Areas Mais Adequadas</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          {careerAdvisory.advisory.suitable_areas.map((area, i) => (
                            <Box key={i} display="flex" alignItems="center" gap={1} mb={1}>
                              <Chip label={`${area.fit_score}%`} size="small" color="primary" />
                              <Typography variant="body2" fontWeight={500}>{area.area}</Typography>
                              <Typography variant="caption" color="text.secondary">- {area.reasoning}</Typography>
                            </Box>
                          ))}
                        </AccordionDetails>
                      </Accordion>
                    )}
                  </Box>
                ) : (
                  /* Quick Tips (heuristic fallback) */
                  <Box>
                    <Typography variant="subtitle2" gutterBottom fontWeight={600}>
                      Dicas Rapidas
                    </Typography>
                    {(careerAdvisory.quick_tips || []).map((tip, i) => (
                      <Alert key={i} severity="info" sx={{ mb: 1 }}>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Chip label={tip.priority} size="small" />
                          <Typography variant="body2">{tip.tip}</Typography>
                        </Box>
                      </Alert>
                    ))}
                    {careerAdvisory.error && (
                      <Alert severity="warning" sx={{ mt: 2 }}>
                        Consultoria completa indisponivel: {careerAdvisory.error}
                      </Alert>
                    )}
                  </Box>
                )}
              </Box>
            </TabPanel>

            {/* Sources Tab (was index 3, now index 6) */}
            <TabPanel value={tab} index={6}>
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

        {/* Right column - Stats & Quality */}
        <Grid item xs={12} md={4}>
          {/* Quality Score Card */}
          {enrichedProfile?.validation && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Qualidade da Extracao
                </Typography>
                <Box display="flex" alignItems="center" gap={2} mt={1} mb={2}>
                  <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                    <CircularProgress
                      variant="determinate"
                      value={(enrichedProfile.validation.overall_confidence || 0) * 100}
                      size={60}
                      thickness={5}
                      color={
                        enrichedProfile.validation.quality_label === 'alta' ? 'success' :
                        enrichedProfile.validation.quality_label === 'media' ? 'warning' : 'error'
                      }
                    />
                    <Box sx={{ top: 0, left: 0, bottom: 0, right: 0, position: 'absolute', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Typography variant="caption" fontWeight={700}>
                        {Math.round((enrichedProfile.validation.overall_confidence || 0) * 100)}%
                      </Typography>
                    </Box>
                  </Box>
                  <Box>
                    <Chip
                      label={enrichedProfile.validation.quality_label || 'N/A'}
                      size="small"
                      color={
                        enrichedProfile.validation.quality_label === 'alta' ? 'success' :
                        enrichedProfile.validation.quality_label === 'media' ? 'warning' : 'error'
                      }
                    />
                    <Typography variant="caption" display="block" color="text.secondary" mt={0.5}>
                      {enrichedProfile.validation.fields_extracted || 0}/{enrichedProfile.validation.total_fields || 0} campos
                    </Typography>
                  </Box>
                </Box>
                {enrichedProfile.ai_enhanced && (
                  <Chip label="IA Validado" size="small" color="primary" icon={<SmartToy />} sx={{ mb: 1 }} />
                )}
                <Typography variant="caption" display="block" color="text.secondary">
                  Metodo: {enrichedProfile.extraction_method}
                </Typography>
              </CardContent>
            </Card>
          )}

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
                  <Typography variant="body2" fontWeight={600}>
                    {enrichedProfile?.experiences?.length || experiences.length}
                  </Typography>
                </Box>
                <Divider />
                <Box display="flex" justifyContent="space-between" py={1}>
                  <Typography variant="body2" color="text.secondary">Skills</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {enrichedProfile?.skills
                      ? (enrichedProfile.skills.technical?.length || 0) +
                        (enrichedProfile.skills.soft?.length || 0) +
                        (enrichedProfile.skills.tools?.length || 0) +
                        (enrichedProfile.skills.frameworks?.length || 0)
                      : 0}
                  </Typography>
                </Box>
                <Divider />
                <Box display="flex" justifyContent="space-between" py={1}>
                  <Typography variant="body2" color="text.secondary">Certificacoes</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {enrichedProfile?.certifications?.length || 0}
                  </Typography>
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
