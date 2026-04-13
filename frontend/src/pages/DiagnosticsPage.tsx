import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Alert,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  CheckCircle,
  Error as ErrorIcon,
  Warning,
  SkipNext,
  PlayArrow,
  ExpandMore,
  Storage,
  Cloud,
  Memory,
  Dns,
  SmartToy,
  FolderOpen,
  LinkedIn,
  Speed,
  Refresh,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';

interface ServiceTest {
  service: string;
  status: string;
  message: string;
  duration_ms: number;
  details: Record<string, any>;
}

interface DiagnosticsResult {
  overall_status: string;
  timestamp: string;
  app_version: string;
  tests: ServiceTest[];
  summary: Record<string, number>;
  recommendations: string[];
}

const statusIcons: Record<string, React.ReactElement> = {
  ok: <CheckCircle color="success" />,
  error: <ErrorIcon color="error" />,
  warning: <Warning color="warning" />,
  skipped: <SkipNext color="disabled" />,
};

const serviceIcons: Record<string, React.ReactElement> = {
  PostgreSQL: <Storage color="primary" />,
  pgvector: <Memory color="secondary" />,
  Redis: <Dns color="error" />,
  'Celery Workers': <Speed color="info" />,
  'OpenAI API (Embeddings)': <Cloud color="success" />,
  'OpenAI Chat (LLM)': <SmartToy color="primary" />,
  'Vector Store': <Memory color="warning" />,
  'Pipeline Embedding (E2E)': <Speed color="success" />,
  'Storage (Arquivos)': <FolderOpen color="action" />,
  'LinkedIn API': <LinkedIn color="primary" />,
};

const DiagnosticsPage: React.FC = () => {
  const { showSuccess, showError } = useNotification();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosticsResult | null>(null);
  const [testingService, setTestingService] = useState<string | null>(null);
  const [singleResult, setSingleResult] = useState<ServiceTest | null>(null);

  const runFullDiagnostics = async () => {
    setLoading(true);
    setSingleResult(null);
    try {
      const data = await apiService.runDiagnostics();
      setResult(data);
      if (data.overall_status === 'healthy') {
        showSuccess('Todos os servicos estao funcionando!');
      } else if (data.overall_status === 'degraded') {
        showError('Alguns servicos precisam de atencao');
      } else {
        showError('Problemas criticos encontrados');
      }
    } catch (err: any) {
      showError('Erro ao executar diagnostico: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const testSingleService = async (serviceName: string) => {
    setTestingService(serviceName);
    try {
      const data = await apiService.testService(serviceName);
      setSingleResult(data);
    } catch (err: any) {
      showError('Erro: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTestingService(null);
    }
  };

  const overallColor = result?.overall_status === 'healthy' ? 'success' : result?.overall_status === 'degraded' ? 'warning' : 'error';

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Diagnostico do Sistema
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Teste todas as conexoes e APIs do sistema para identificar problemas.
      </Typography>

      <Grid container spacing={3}>
        {/* Main controls */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              size="large"
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrow />}
              onClick={runFullDiagnostics}
              disabled={loading}
            >
              {loading ? 'Executando...' : 'Executar Diagnostico Completo'}
            </Button>

            {result && (
              <Chip
                label={`Status: ${result.overall_status.toUpperCase()}`}
                color={overallColor as any}
                variant="filled"
                sx={{ fontWeight: 600, fontSize: '0.9rem' }}
              />
            )}

            {result && (
              <Box display="flex" gap={1} ml="auto">
                <Chip label={`${result.summary.ok || 0} OK`} color="success" size="small" variant="outlined" />
                <Chip label={`${result.summary.warning || 0} Avisos`} color="warning" size="small" variant="outlined" />
                <Chip label={`${result.summary.error || 0} Erros`} color="error" size="small" variant="outlined" />
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Individual service tests */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Testar Individualmente
              </Typography>
              <List dense>
                {[
                  { key: 'database', label: 'PostgreSQL' },
                  { key: 'pgvector', label: 'pgvector' },
                  { key: 'redis', label: 'Redis' },
                  { key: 'celery', label: 'Celery Workers' },
                  { key: 'openai', label: 'OpenAI Embeddings' },
                  { key: 'openai_chat', label: 'OpenAI Chat' },
                  { key: 'vector_store', label: 'Vector Store' },
                  { key: 'embedding_pipeline', label: 'Pipeline E2E' },
                  { key: 'storage', label: 'Storage' },
                  { key: 'linkedin', label: 'LinkedIn' },
                ].map((svc) => (
                  <ListItem
                    key={svc.key}
                    secondaryAction={
                      <Button
                        size="small"
                        onClick={() => testSingleService(svc.key)}
                        disabled={testingService === svc.key}
                        startIcon={testingService === svc.key ? <CircularProgress size={14} /> : <Refresh />}
                      >
                        Testar
                      </Button>
                    }
                  >
                    <ListItemText primary={svc.label} primaryTypographyProps={{ variant: 'body2' }} />
                  </ListItem>
                ))}
              </List>

              {singleResult && (
                <Alert severity={singleResult.status === 'ok' ? 'success' : singleResult.status === 'warning' ? 'warning' : 'error'} sx={{ mt: 2 }}>
                  <Typography variant="body2" fontWeight={600}>{singleResult.service}</Typography>
                  <Typography variant="body2">{singleResult.message}</Typography>
                  <Typography variant="caption">Tempo: {singleResult.duration_ms}ms</Typography>
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Results */}
        <Grid item xs={12} md={8}>
          {result ? (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Resultados do Diagnostico
              </Typography>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block" sx={{ mb: 2 }}>
                Versao: {result.app_version} | {new Date(result.timestamp).toLocaleString('pt-BR')}
              </Typography>

              {result.recommendations.length > 0 && (
                <Alert severity="info" sx={{ mb: 3 }}>
                  <Typography variant="body2" fontWeight={600} gutterBottom>Recomendacoes:</Typography>
                  {result.recommendations.map((rec, i) => (
                    <Typography key={i} variant="body2">- {rec}</Typography>
                  ))}
                </Alert>
              )}

              {result.tests.map((test, idx) => (
                <Accordion key={idx} defaultExpanded={test.status !== 'ok'}>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Box display="flex" alignItems="center" gap={1.5} width="100%">
                      {serviceIcons[test.service] || statusIcons[test.status]}
                      <Typography fontWeight={500} sx={{ flexGrow: 1 }}>{test.service}</Typography>
                      <Chip
                        label={test.status.toUpperCase()}
                        size="small"
                        color={test.status === 'ok' ? 'success' : test.status === 'warning' ? 'warning' : test.status === 'error' ? 'error' : 'default'}
                        variant="outlined"
                      />
                      <Typography variant="caption" color="text.secondary">{test.duration_ms}ms</Typography>
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography variant="body2" gutterBottom>{test.message}</Typography>
                    {Object.keys(test.details).length > 0 && (
                      <Box sx={{ mt: 1, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                        <pre style={{ margin: 0, fontSize: '0.75rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                          {JSON.stringify(test.details, null, 2)}
                        </pre>
                      </Box>
                    )}
                  </AccordionDetails>
                </Accordion>
              ))}
            </Paper>
          ) : (
            <Paper sx={{ p: 6, textAlign: 'center' }}>
              <Storage sx={{ fontSize: 64, color: 'text.secondary', mb: 2, opacity: 0.4 }} />
              <Typography variant="h6" color="text.secondary">
                Clique em "Executar Diagnostico Completo" para verificar todas as conexoes
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                O sistema testara PostgreSQL, pgvector, Redis, Celery, OpenAI, Vector Store, Storage e LinkedIn
              </Typography>
            </Paper>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default DiagnosticsPage;
