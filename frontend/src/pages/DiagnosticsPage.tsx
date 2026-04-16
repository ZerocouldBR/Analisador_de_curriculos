import React, { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  Chip,
  Divider,
  IconButton,
  Tooltip,
  Collapse,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  PlayArrow,
  Storage,
  Memory,
  Psychology,
  Hub,
  Settings,
  DataArray,
  CheckCircle,
  Warning,
  Error as ErrorIcon,
  Info,
  ExpandMore,
  ExpandLess,
  Refresh,
  Terminal,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';

interface ComponentResult {
  component?: string;
  name?: string;
  status: string;
  message: string;
  elapsed_ms: number;
  details: Record<string, any>;
}

const statusIcon = (status: string) => {
  switch (status) {
    case 'ok':
      return <CheckCircle sx={{ color: 'success.main' }} />;
    case 'warning':
    case 'not_configured':
      return <Warning sx={{ color: 'warning.main' }} />;
    case 'error':
      return <ErrorIcon sx={{ color: 'error.main' }} />;
    default:
      return <Info sx={{ color: 'text.secondary' }} />;
  }
};

const statusColor = (status: string): 'success' | 'warning' | 'error' | 'default' => {
  switch (status) {
    case 'ok': return 'success';
    case 'warning':
    case 'not_configured': return 'warning';
    case 'error': return 'error';
    default: return 'default';
  }
};

const ComponentCard: React.FC<{
  result: ComponentResult;
  icon: React.ReactElement;
}> = ({ result, icon }) => {
  const [expanded, setExpanded] = useState(false);
  const name = result.component || result.name || 'Componente';

  return (
    <Card sx={{ border: '1px solid', borderColor: 'divider' }}>
      <CardContent sx={{ pb: expanded ? 2 : '16px !important' }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box display="flex" alignItems="center" gap={1.5}>
            <Box sx={{ color: 'primary.main' }}>{icon}</Box>
            {statusIcon(result.status)}
            <Box>
              <Typography variant="body1" fontWeight={600}>{name}</Typography>
              <Typography variant="caption" color="text.secondary">
                {result.message}
              </Typography>
            </Box>
          </Box>
          <Box display="flex" alignItems="center" gap={1}>
            {result.elapsed_ms > 0 && (
              <Chip
                label={`${result.elapsed_ms.toFixed(0)}ms`}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.7rem', height: 22 }}
              />
            )}
            <Chip label={result.status} size="small" color={statusColor(result.status)} sx={{ fontSize: '0.7rem', height: 22 }} />
            {Object.keys(result.details).length > 0 && (
              <IconButton size="small" onClick={() => setExpanded(!expanded)}>
                {expanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
              </IconButton>
            )}
          </Box>
        </Box>

        <Collapse in={expanded}>
          <Box sx={{ mt: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1, maxHeight: 300, overflow: 'auto' }}>
            <pre style={{ margin: 0, fontSize: '0.75rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {JSON.stringify(result.details, null, 2)}
            </pre>
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
};

const componentIcons: Record<string, React.ReactElement> = {
  'PostgreSQL Database': <Storage />,
  'Redis': <Memory />,
  'OpenAI API': <Psychology />,
  'Openai API': <Psychology />,
  'Anthropic API': <Psychology />,
  'LLM': <Psychology />,
  'Celery Task Queue': <Settings />,
  'Embedding Pipeline': <DataArray />,
  'Configuracoes': <Settings />,
};

const getComponentIcon = (name: string): React.ReactElement => {
  for (const [key, icon] of Object.entries(componentIcons)) {
    if (name.includes(key)) return icon;
  }
  if (name.includes('Vector')) return <Hub />;
  return <Info />;
};

const individualTests = [
  { key: 'database', label: 'PostgreSQL', icon: <Storage fontSize="small" />, fn: () => apiService.testDatabaseConnection() },
  { key: 'redis', label: 'Redis', icon: <Memory fontSize="small" />, fn: () => apiService.testRedisConnection() },
  { key: 'openai', label: 'LLM API', icon: <Psychology fontSize="small" />, fn: () => apiService.testOpenAIConnection() },
  { key: 'vectorstore', label: 'Vector Store', icon: <Hub fontSize="small" />, fn: () => apiService.testVectorStoreConnection() },
  { key: 'celery', label: 'Celery', icon: <Settings fontSize="small" />, fn: () => apiService.testCeleryConnection() },
  { key: 'embedding', label: 'Embedding Pipeline', icon: <DataArray fontSize="small" />, fn: () => apiService.testEmbeddingPipeline() },
];

const DiagnosticsPage: React.FC = () => {
  const { showError } = useNotification();
  const [fullResult, setFullResult] = useState<any>(null);
  const [runningFull, setRunningFull] = useState(false);
  const [individualResults, setIndividualResults] = useState<Record<string, ComponentResult>>({});
  const [runningIndividual, setRunningIndividual] = useState<string | null>(null);

  // Logs state
  const [logs, setLogs] = useState<any>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logLines, setLogLines] = useState(100);
  const [logLevel, setLogLevel] = useState('all');

  const handleRunFullDiagnostics = useCallback(async () => {
    setRunningFull(true);
    setFullResult(null);
    try {
      const result = await apiService.runFullDiagnostics();
      setFullResult(result);
    } catch (e: any) {
      showError('Erro ao executar diagnostico: ' + (e.response?.data?.detail || String(e)));
    } finally {
      setRunningFull(false);
    }
  }, [showError]);

  const handleRunIndividual = async (key: string, fn: () => Promise<any>) => {
    setRunningIndividual(key);
    try {
      const result = await fn();
      setIndividualResults((prev) => ({ ...prev, [key]: result }));
    } catch (e: any) {
      setIndividualResults((prev) => ({
        ...prev,
        [key]: {
          component: key,
          status: 'error',
          message: e.response?.data?.detail || String(e),
          elapsed_ms: 0,
          details: {},
        },
      }));
    } finally {
      setRunningIndividual(null);
    }
  };

  const handleFetchLogs = async () => {
    setLoadingLogs(true);
    try {
      const result = await apiService.getRecentLogs(logLines, logLevel);
      setLogs(result);
    } catch (e: any) {
      showError('Erro ao carregar logs: ' + (e.response?.data?.detail || String(e)));
    } finally {
      setLoadingLogs(false);
    }
  };

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Diagnostico do Sistema
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Teste conexoes, verifique componentes e visualize logs do sistema
          </Typography>
        </Box>
        <Button
          variant="contained"
          size="large"
          onClick={handleRunFullDiagnostics}
          disabled={runningFull}
          startIcon={runningFull ? <CircularProgress size={20} color="inherit" /> : <PlayArrow />}
        >
          {runningFull ? 'Executando...' : 'Diagnostico Completo'}
        </Button>
      </Box>

      {/* Full diagnostics result */}
      {fullResult && (
        <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Box display="flex" alignItems="center" gap={1.5}>
              <Typography variant="h6" fontWeight={600}>Resultado do Diagnostico</Typography>
              <Chip
                label={fullResult.overall_status === 'ok' ? 'Tudo OK' :
                       fullResult.overall_status === 'degraded' ? 'Degradado' : 'Erro'}
                color={statusColor(fullResult.overall_status === 'degraded' ? 'warning' : fullResult.overall_status)}
                size="small"
              />
            </Box>
            <Box display="flex" gap={1}>
              {fullResult.summary && Object.entries(fullResult.summary).map(([key, val]) => (
                val as number > 0 && (
                  <Chip
                    key={key}
                    label={`${key}: ${val}`}
                    size="small"
                    color={statusColor(key)}
                    variant="outlined"
                    sx={{ fontSize: '0.7rem' }}
                  />
                )
              ))}
            </Box>
          </Box>

          <Typography variant="caption" color="text.secondary" display="block" mb={2}>
            v{fullResult.version} | {new Date(fullResult.timestamp).toLocaleString()}
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {fullResult.components?.map((comp: any, i: number) => (
              <ComponentCard
                key={i}
                result={comp}
                icon={getComponentIcon(comp.name || '')}
              />
            ))}
          </Box>
        </Paper>
      )}

      {/* Individual tests */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Testes Individuais
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Teste cada componente individualmente para diagnosticar problemas especificos
        </Typography>

        <Grid container spacing={2}>
          {individualTests.map((test) => (
            <Grid item xs={12} sm={6} md={4} key={test.key}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Box display="flex" alignItems="center" gap={1}>
                      {test.icon}
                      <Typography variant="body2" fontWeight={600}>{test.label}</Typography>
                    </Box>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => handleRunIndividual(test.key, test.fn)}
                      disabled={runningIndividual === test.key}
                      startIcon={runningIndividual === test.key ? <CircularProgress size={14} /> : <PlayArrow />}
                      sx={{ minWidth: 90 }}
                    >
                      Testar
                    </Button>
                  </Box>

                  {individualResults[test.key] && (
                    <Box sx={{ mt: 1 }}>
                      <Alert
                        severity={individualResults[test.key].status === 'ok' ? 'success' :
                                  individualResults[test.key].status === 'warning' || individualResults[test.key].status === 'not_configured' ? 'warning' : 'error'}
                        sx={{ '& .MuiAlert-message': { fontSize: '0.75rem' } }}
                      >
                        <Box>
                          <strong>{individualResults[test.key].message}</strong>
                          {individualResults[test.key].elapsed_ms > 0 && (
                            <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                              Tempo: {individualResults[test.key].elapsed_ms.toFixed(0)}ms
                            </Typography>
                          )}
                        </Box>
                      </Alert>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* Logs viewer */}
      <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Terminal />
            <Typography variant="h6" fontWeight={600}>Logs da Aplicacao</Typography>
          </Box>
          <Box display="flex" gap={1} alignItems="center">
            <TextField
              size="small"
              type="number"
              label="Linhas"
              value={logLines}
              onChange={(e) => setLogLines(Math.min(500, parseInt(e.target.value) || 100))}
              sx={{ width: 90 }}
              inputProps={{ min: 10, max: 500 }}
            />
            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Nivel</InputLabel>
              <Select value={logLevel} label="Nivel" onChange={(e) => setLogLevel(e.target.value)}>
                <MenuItem value="all">Todos</MenuItem>
                <MenuItem value="error">Erros</MenuItem>
                <MenuItem value="warning">Avisos</MenuItem>
                <MenuItem value="info">Info</MenuItem>
              </Select>
            </FormControl>
            <Button
              variant="outlined"
              size="small"
              onClick={handleFetchLogs}
              disabled={loadingLogs}
              startIcon={loadingLogs ? <CircularProgress size={14} /> : <Refresh />}
            >
              Carregar
            </Button>
          </Box>
        </Box>

        {logs && (
          <Box>
            <Typography variant="caption" color="text.secondary" mb={1} display="block">
              Arquivo: {logs.log_file} | Total: {logs.total_lines} linhas | Exibindo: {logs.returned_lines}
            </Typography>
            <Box
              sx={{
                maxHeight: 400,
                overflow: 'auto',
                bgcolor: 'grey.900',
                color: 'grey.100',
                p: 2,
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: '0.72rem',
                lineHeight: 1.6,
              }}
            >
              {logs.lines?.length > 0 ? (
                logs.lines.map((line: string, i: number) => (
                  <Box
                    key={i}
                    sx={{
                      color: line.includes('ERROR') ? 'error.light' :
                             line.includes('WARNING') ? 'warning.light' :
                             line.includes('INFO') ? 'info.light' : 'grey.300',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {line}
                  </Box>
                ))
              ) : (
                <Typography variant="body2" color="grey.500">
                  {logs.message || 'Nenhum log encontrado'}
                </Typography>
              )}
            </Box>
          </Box>
        )}

        {!logs && (
          <Alert severity="info">
            Clique em "Carregar" para visualizar os logs recentes da aplicacao
          </Alert>
        )}
      </Paper>
    </Box>
  );
};

export default DiagnosticsPage;
