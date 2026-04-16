import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Chip,
  Card,
  CardContent,
  Grid,
  Tab,
  Tabs,
  IconButton,
  Tooltip,
  Alert,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  FormHelperText,
  InputAdornment,
  CircularProgress,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Memory,
  Storage,
  Security,
  Refresh,
  CheckCircle,
  Warning,
  Save,
  RestartAlt,
  Psychology,
  Hub,
  Chat,
  Search,
  WorkOutline,
  DocumentScanner,
  ViewModule,
  CloudUpload,
  AttachMoney,
  LinkedIn,
  Visibility,
  VisibilityOff,
  Info,
  NetworkCheck,
  FiberManualRecord,
  SmartToy,
  Label,
  BuildCircle,
  Delete,
  Add,
  TableChart,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import {
  HealthCheck,
  SystemConfigResponse,
  SystemConfigCategory,
  SystemConfigField,
} from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { TableSkeleton } from '../components/LoadingSkeleton';

// Map icon names to MUI icon components
const iconMap: Record<string, React.ReactElement> = {
  Settings: <SettingsIcon />,
  Storage: <Storage />,
  Memory: <Memory />,
  Psychology: <Psychology />,
  Hub: <Hub />,
  Chat: <Chat />,
  Search: <Search />,
  WorkOutline: <WorkOutline />,
  DocumentScanner: <DocumentScanner />,
  ViewModule: <ViewModule />,
  CloudUpload: <CloudUpload />,
  Security: <Security />,
  AttachMoney: <AttachMoney />,
  LinkedIn: <LinkedIn />,
  SmartToy: <SmartToy />,
  Label: <Label />,
};

// Model label map for better display in dropdowns
const MODEL_LABELS: Record<string, string> = {
  // OpenAI LLM
  'gpt-4o': 'GPT-4o (recomendado)',
  'gpt-4o-mini': 'GPT-4o Mini (economico)',
  'gpt-4-turbo': 'GPT-4 Turbo',
  'gpt-4': 'GPT-4',
  'gpt-3.5-turbo': 'GPT-3.5 Turbo',
  'o3-mini': 'o3-mini (raciocinio)',
  // Anthropic LLM
  'claude-sonnet-4-20250514': 'Claude Sonnet 4 (recomendado)',
  'claude-opus-4-20250514': 'Claude Opus 4',
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku (economico)',
  'claude-3-opus-20240229': 'Claude 3 Opus',
  // OpenAI Embeddings
  'text-embedding-3-small': 'text-embedding-3-small (1536 dims)',
  'text-embedding-3-large': 'text-embedding-3-large (3072 dims)',
  'text-embedding-ada-002': 'text-embedding-ada-002 (legado)',
  // Local Embeddings
  'all-MiniLM-L6-v2': 'all-MiniLM-L6-v2 (384 dims, rapido)',
  'all-MiniLM-L12-v2': 'all-MiniLM-L12-v2 (384 dims)',
  'all-mpnet-base-v2': 'all-mpnet-base-v2 (768 dims, melhor qualidade)',
  'paraphrase-multilingual-MiniLM-L12-v2': 'multilingual-MiniLM-L12-v2 (384 dims, multi-idioma)',
  'multi-qa-MiniLM-L6-cos-v1': 'multi-qa-MiniLM-L6 (384 dims, Q&A)',
};

// Field renderer component
const ConfigFieldRenderer: React.FC<{
  field: SystemConfigField;
  value: any;
  onChange: (key: string, value: any) => void;
  allValues?: Record<string, any>;
}> = ({ field, value, onChange, allValues }) => {
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (newValue: any) => {
    onChange(field.key, newValue);
  };

  // Resolve options: use options_map if depends_on is set
  const resolveOptions = (): string[] => {
    if (field.depends_on && field.options_map && allValues) {
      const depValue = allValues[field.depends_on];
      return field.options_map[depValue] || field.options || [];
    }
    return field.options || [];
  };

  switch (field.type) {
    case 'boolean':
      return (
        <FormControlLabel
          control={
            <Switch
              checked={!!value}
              onChange={(e) => handleChange(e.target.checked)}
              color="primary"
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight={500}>
                {field.label}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {field.description}
              </Typography>
            </Box>
          }
          sx={{ ml: 0, width: '100%', alignItems: 'flex-start' }}
        />
      );

    case 'select': {
      const options = resolveOptions();
      const isCustomValue = value && !options.includes(value);
      const allOptions = isCustomValue ? [...options, value] : options;
      return (
        <FormControl fullWidth size="small">
          <InputLabel>{field.label}</InputLabel>
          <Select
            value={allOptions.includes(value) ? value : (value ?? '')}
            label={field.label}
            onChange={(e) => handleChange(e.target.value)}
          >
            {options.map((opt) => (
              <MenuItem key={opt} value={opt}>
                {MODEL_LABELS[opt] || opt}
              </MenuItem>
            ))}
            {/* Show current value even if not in options list (custom/legacy model) */}
            {isCustomValue && (
              <MenuItem key={value} value={value}>
                {value} (personalizado)
              </MenuItem>
            )}
          </Select>
          <FormHelperText>{field.description}</FormHelperText>
        </FormControl>
      );
    }

    case 'password':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          type={showPassword ? 'text' : 'password'}
          value={value ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={field.description}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={() => setShowPassword(!showPassword)}
                  edge="end"
                >
                  {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      );

    case 'number':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          type="number"
          value={value ?? ''}
          onChange={(e) => {
            const v = e.target.value;
            if (v === '') {
              handleChange('');
              return;
            }
            handleChange(
              field.step !== undefined && field.step < 1
                ? parseFloat(v)
                : parseInt(v, 10)
            );
          }}
          inputProps={{
            min: field.min_value,
            max: field.max_value,
            step: field.step,
          }}
          placeholder={field.placeholder}
          helperText={field.description}
        />
      );

    case 'textarea':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          multiline
          rows={4}
          value={value ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={field.description}
        />
      );

    case 'list_int':
    case 'list_str':
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          value={Array.isArray(value) ? value.join(', ') : (value ?? '')}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={`${field.description} (separe com virgula)`}
        />
      );

    default: // text
      return (
        <TextField
          fullWidth
          size="small"
          label={field.label}
          value={value ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={field.placeholder}
          helperText={field.description}
        />
      );
  }
};

// Field wrapper with override/restart indicators
const FieldWrapper: React.FC<{
  field: SystemConfigField;
  overrideKeys: string[];
  editedValues: Record<string, any>;
  onChange: (key: string, value: any) => void;
}> = ({ field, overrideKeys, editedValues, onChange }) => (
  <Box
    sx={{
      p: 2,
      borderRadius: 1,
      border: '1px solid',
      borderColor: overrideKeys.includes(field.key) ? 'primary.main' : 'divider',
      bgcolor: overrideKeys.includes(field.key) ? 'action.selected' : 'transparent',
      position: 'relative',
    }}
  >
    {field.restart_required && (
      <Tooltip title="Requer reiniciar os servicos">
        <Chip
          label="restart"
          size="small"
          color="warning"
          variant="outlined"
          sx={{ position: 'absolute', top: 8, right: 8, fontSize: '0.65rem', height: 20 }}
        />
      </Tooltip>
    )}
    <ConfigFieldRenderer
      field={field}
      value={editedValues[field.key]}
      onChange={onChange}
      allValues={editedValues}
    />
  </Box>
);

// Status dot for provider tabs
const StatusDot: React.FC<{
  enabled: boolean;
  testStatus?: string;
}> = ({ enabled, testStatus }) => {
  let color = 'grey.400'; // disabled
  if (enabled && testStatus === 'ok') {
    color = 'success.main';
  } else if (enabled && testStatus === 'error') {
    color = 'error.main';
  } else if (enabled) {
    color = 'warning.main';
  }

  return (
    <FiberManualRecord sx={{ fontSize: 12, color }} />
  );
};

// Index management component for pgvector
const IndexManager: React.FC = () => {
  const [indexes, setIndexes] = useState<any[]>([]);
  const [loadingIndexes, setLoadingIndexes] = useState(false);
  const [creatingIndex, setCreatingIndex] = useState(false);
  const [deletingIndex, setDeletingIndex] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [indexAlert, setIndexAlert] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Create index form state
  const [newIndex, setNewIndex] = useState({
    table_name: 'embeddings',
    column_name: 'vector',
    index_type: 'hnsw',
    distance_ops: 'vector_cosine_ops',
    index_name: '',
    hnsw_m: 16,
    hnsw_ef_construction: 64,
  });

  const fetchIndexes = useCallback(async () => {
    setLoadingIndexes(true);
    try {
      const data = await apiService.listIndexes();
      setIndexes(data.indexes || []);
    } catch (e: any) {
      setIndexAlert({ type: 'error', message: 'Erro ao carregar indices: ' + (e.response?.data?.detail || String(e)) });
    } finally {
      setLoadingIndexes(false);
    }
  }, []);

  useEffect(() => { fetchIndexes(); }, [fetchIndexes]);

  const handleCreateIndex = async () => {
    setCreatingIndex(true);
    setIndexAlert(null);
    try {
      const payload: any = {
        table_name: newIndex.table_name,
        column_name: newIndex.column_name,
        index_type: newIndex.index_type,
      };
      if (newIndex.index_type === 'hnsw' || newIndex.index_type === 'ivfflat') {
        payload.distance_ops = newIndex.distance_ops;
      }
      if (newIndex.index_type === 'hnsw') {
        payload.hnsw_m = newIndex.hnsw_m;
        payload.hnsw_ef_construction = newIndex.hnsw_ef_construction;
      }
      if (newIndex.index_name.trim()) {
        payload.index_name = newIndex.index_name.trim();
      }

      const result = await apiService.createIndex(payload);
      if (result.success) {
        setIndexAlert({ type: 'success', message: result.message });
        setShowCreateForm(false);
        setNewIndex({ table_name: 'embeddings', column_name: 'vector', index_type: 'hnsw', distance_ops: 'vector_cosine_ops', index_name: '', hnsw_m: 16, hnsw_ef_construction: 64 });
        await fetchIndexes();
      } else {
        setIndexAlert({ type: 'error', message: result.message });
      }
    } catch (e: any) {
      setIndexAlert({ type: 'error', message: 'Erro: ' + (e.response?.data?.detail || String(e)) });
    } finally {
      setCreatingIndex(false);
    }
  };

  const handleDeleteIndex = async (indexName: string) => {
    setDeletingIndex(indexName);
    setIndexAlert(null);
    try {
      await apiService.deleteIndex(indexName);
      setIndexAlert({ type: 'success', message: `Indice '${indexName}' removido com sucesso` });
      await fetchIndexes();
    } catch (e: any) {
      setIndexAlert({ type: 'error', message: 'Erro: ' + (e.response?.data?.detail || String(e)) });
    } finally {
      setDeletingIndex(null);
    }
  };

  const isVectorIndex = newIndex.index_type === 'hnsw' || newIndex.index_type === 'ivfflat';

  return (
    <Box sx={{ mt: 3 }}>
      <Divider sx={{ mb: 3 }} />
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Box>
          <Typography variant="subtitle1" fontWeight={600}>
            <TableChart fontSize="small" sx={{ mr: 1, verticalAlign: 'middle' }} />
            Gerenciamento de Indices
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Visualize, crie e gerencie indices do banco vetorial
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            size="small"
            onClick={fetchIndexes}
            disabled={loadingIndexes}
            startIcon={loadingIndexes ? <CircularProgress size={16} /> : <Refresh />}
          >
            Atualizar
          </Button>
          <Button
            variant="contained"
            size="small"
            onClick={() => setShowCreateForm(!showCreateForm)}
            startIcon={<Add />}
            color={showCreateForm ? 'inherit' : 'primary'}
          >
            {showCreateForm ? 'Cancelar' : 'Novo Indice'}
          </Button>
        </Box>
      </Box>

      {indexAlert && (
        <Alert severity={indexAlert.type} sx={{ mb: 2 }} onClose={() => setIndexAlert(null)}>
          {indexAlert.message}
        </Alert>
      )}

      {/* Create index form */}
      {showCreateForm && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'action.hover' }}>
          <Typography variant="subtitle2" fontWeight={600} mb={2}>
            Criar Novo Indice
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Tabela</InputLabel>
                <Select value={newIndex.table_name} label="Tabela"
                  onChange={(e) => setNewIndex((p) => ({ ...p, table_name: e.target.value }))}
                >
                  <MenuItem value="embeddings">embeddings</MenuItem>
                  <MenuItem value="chunks">chunks</MenuItem>
                  <MenuItem value="candidates">candidates</MenuItem>
                  <MenuItem value="documents">documents</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField fullWidth size="small" label="Coluna"
                value={newIndex.column_name}
                onChange={(e) => setNewIndex((p) => ({ ...p, column_name: e.target.value }))}
                helperText="Ex: vector, embedding, content"
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Tipo de Indice</InputLabel>
                <Select value={newIndex.index_type} label="Tipo de Indice"
                  onChange={(e) => setNewIndex((p) => ({ ...p, index_type: e.target.value }))}
                >
                  <MenuItem value="hnsw">HNSW (vetorial - recomendado)</MenuItem>
                  <MenuItem value="ivfflat">IVFFlat (vetorial)</MenuItem>
                  <MenuItem value="gin">GIN (full-text / JSON)</MenuItem>
                  <MenuItem value="btree">B-Tree (geral)</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {isVectorIndex && (
              <Grid item xs={12} md={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Operador de Distancia</InputLabel>
                  <Select value={newIndex.distance_ops} label="Operador de Distancia"
                    onChange={(e) => setNewIndex((p) => ({ ...p, distance_ops: e.target.value }))}
                  >
                    <MenuItem value="vector_cosine_ops">Cosine (vector_cosine_ops)</MenuItem>
                    <MenuItem value="vector_l2_ops">L2 / Euclidean (vector_l2_ops)</MenuItem>
                    <MenuItem value="vector_ip_ops">Inner Product (vector_ip_ops)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            )}

            {newIndex.index_type === 'hnsw' && (
              <>
                <Grid item xs={6} md={4}>
                  <TextField fullWidth size="small" label="HNSW M" type="number"
                    value={newIndex.hnsw_m}
                    onChange={(e) => setNewIndex((p) => ({ ...p, hnsw_m: parseInt(e.target.value) || 16 }))}
                    helperText="Conexoes por no (padrao: 16)"
                    inputProps={{ min: 2, max: 100 }}
                  />
                </Grid>
                <Grid item xs={6} md={4}>
                  <TextField fullWidth size="small" label="EF Construction" type="number"
                    value={newIndex.hnsw_ef_construction}
                    onChange={(e) => setNewIndex((p) => ({ ...p, hnsw_ef_construction: parseInt(e.target.value) || 64 }))}
                    helperText="Qualidade da construcao (padrao: 64)"
                    inputProps={{ min: 16, max: 500 }}
                  />
                </Grid>
              </>
            )}

            <Grid item xs={12} md={isVectorIndex ? 12 : 4}>
              <TextField fullWidth size="small" label="Nome do Indice (opcional)"
                value={newIndex.index_name}
                onChange={(e) => setNewIndex((p) => ({ ...p, index_name: e.target.value }))}
                helperText="Deixe vazio para gerar automaticamente"
              />
            </Grid>

            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={handleCreateIndex}
                disabled={creatingIndex || !newIndex.column_name}
                startIcon={creatingIndex ? <CircularProgress size={16} /> : <Add />}
              >
                {creatingIndex ? 'Criando...' : 'Criar Indice'}
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Existing indexes list */}
      {loadingIndexes ? (
        <Box display="flex" justifyContent="center" p={3}>
          <CircularProgress size={24} />
        </Box>
      ) : indexes.length === 0 ? (
        <Alert severity="info">Nenhum indice encontrado. Use o botao "Instalar e Configurar" acima para criar os indices automaticamente.</Alert>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {indexes.map((idx) => (
            <Paper key={idx.indexname} variant="outlined" sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                  <Typography variant="body2" fontWeight={600}>{idx.indexname}</Typography>
                  <Chip label={idx.tablename} size="small" variant="outlined" sx={{ fontSize: '0.65rem', height: 18 }} />
                  {idx.indexdef?.includes('hnsw') && <Chip label="HNSW" size="small" color="primary" variant="outlined" sx={{ fontSize: '0.65rem', height: 18 }} />}
                  {idx.indexdef?.includes('gin') && <Chip label="GIN" size="small" color="secondary" variant="outlined" sx={{ fontSize: '0.65rem', height: 18 }} />}
                  {idx.indexdef?.includes('btree') && <Chip label="B-Tree" size="small" variant="outlined" sx={{ fontSize: '0.65rem', height: 18 }} />}
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: '0.7rem', wordBreak: 'break-all' }}>
                  {idx.indexdef}
                </Typography>
              </Box>
              {!idx.indexname.endsWith('_pkey') && (
                <Tooltip title="Remover indice">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => handleDeleteIndex(idx.indexname)}
                    disabled={deletingIndex === idx.indexname}
                  >
                    {deletingIndex === idx.indexname ? <CircularProgress size={16} /> : <Delete fontSize="small" />}
                  </IconButton>
                </Tooltip>
              )}
            </Paper>
          ))}
        </Box>
      )}
    </Box>
  );
};


// Grouped category renderer for categories with sub-groups (e.g., vector_db)
const GroupedCategoryRenderer: React.FC<{
  category: SystemConfigCategory;
  editedValues: Record<string, any>;
  onChange: (key: string, value: any) => void;
  overrideKeys: string[];
  hasChanges: boolean;
  saving: boolean;
  onSave: () => void;
}> = ({ category, editedValues, onChange, overrideKeys, hasChanges, saving, onSave }) => {
  const [activeGroup, setActiveGroup] = useState(0);
  const [testResults, setTestResults] = useState<Record<string, any>>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [settingUp, setSettingUp] = useState(false);
  const [setupResult, setSetupResult] = useState<any>(null);

  const groups = category.groups || [];
  const globalFields = category.fields.filter((f) => !f.group);
  const getGroupFields = (groupKey: string) =>
    category.fields.filter((f) => f.group === groupKey);

  const handleTestConnection = async (providerName: string) => {
    setTesting(providerName);
    try {
      const result = await apiService.testVectorDBConnection(providerName);
      setTestResults((prev) => ({ ...prev, [providerName]: result }));
    } catch (e: any) {
      setTestResults((prev) => ({
        ...prev,
        [providerName]: {
          status: 'error',
          details: { error: e.response?.data?.detail || String(e) },
        },
      }));
    } finally {
      setTesting(null);
    }
  };

  const handleSetupPgvector = async () => {
    setSettingUp(true);
    setSetupResult(null);
    try {
      const result = await apiService.setupPgvector();
      setSetupResult(result);
      // Refresh test status after setup
      if (result.success) {
        handleTestConnection('pgvector');
      }
    } catch (e: any) {
      setSetupResult({
        success: false,
        message: e.response?.data?.detail || String(e),
        steps: [],
      });
    } finally {
      setSettingUp(false);
    }
  };

  const isSuccessStatus = (s: string) => ['ok', 'healthy', 'connected'].includes(s);

  return (
    <>
      {/* Global fields (e.g., primary provider selector) */}
      {globalFields.length > 0 && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {globalFields.map((field) => (
            <Grid item xs={12} md={6} key={field.key}>
              <FieldWrapper
                field={field}
                overrideKeys={overrideKeys}
                editedValues={editedValues}
                onChange={onChange}
              />
            </Grid>
          ))}
        </Grid>
      )}

      {/* Provider sub-tabs */}
      <Tabs
        value={activeGroup}
        onChange={(_, v) => setActiveGroup(v)}
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        {groups.map((g) => {
          const enabledKey = `${g.key}_enabled`;
          const isEnabled = !!editedValues[enabledKey];
          const testResult = testResults[g.key];
          return (
            <Tab
              key={g.key}
              label={
                <Box display="flex" alignItems="center" gap={0.5}>
                  <StatusDot enabled={isEnabled} testStatus={testResult?.status} />
                  <span>{g.label}</span>
                  {editedValues.vector_db_primary === g.key && (
                    <Chip label="primario" size="small" color="info" variant="outlined"
                      sx={{ ml: 0.5, fontSize: '0.6rem', height: 18 }} />
                  )}
                </Box>
              }
              sx={{ minHeight: 48 }}
            />
          );
        })}
      </Tabs>

      {/* Active group panel */}
      {groups.map((g, idx) =>
        activeGroup === idx ? (
          <Paper key={g.key} variant="outlined" sx={{ p: 3 }}>
            {/* Group header with test button and setup button */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Box>
                <Typography variant="subtitle1" fontWeight={600}>
                  {g.label}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {g.description}
                </Typography>
              </Box>
              <Box display="flex" gap={1}>
                {g.key === 'pgvector' && (
                  <Button
                    variant="contained"
                    size="small"
                    color="success"
                    onClick={handleSetupPgvector}
                    disabled={settingUp}
                    startIcon={
                      settingUp
                        ? <CircularProgress size={16} color="inherit" />
                        : <BuildCircle />
                    }
                  >
                    {settingUp ? 'Configurando...' : 'Instalar e Configurar'}
                  </Button>
                )}
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => handleTestConnection(g.key)}
                  disabled={testing === g.key}
                  startIcon={
                    testing === g.key
                      ? <CircularProgress size={16} />
                      : <NetworkCheck />
                  }
                >
                  Testar Conexao
                </Button>
              </Box>
            </Box>

            {/* Connection test result */}
            {testResults[g.key] && (
              <Alert
                severity={isSuccessStatus(testResults[g.key].status) ? 'success' : 'error'}
                sx={{ mb: 2 }}
                onClose={() =>
                  setTestResults((prev) => {
                    const next = { ...prev };
                    delete next[g.key];
                    return next;
                  })
                }
              >
                {isSuccessStatus(testResults[g.key].status) ? (
                  <Box>
                    <strong>Conexao bem-sucedida!</strong>
                    {testResults[g.key].details?.pgvector_version && (
                      <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                        pgvector v{testResults[g.key].details.pgvector_version}
                        {' | '}{testResults[g.key].details.embeddings_count ?? 0} embeddings
                        {' | '}{testResults[g.key].details.distance_metric ?? 'cosine'}
                        {' | '}{testResults[g.key].details.dimensions ?? '?'} dimensoes
                      </Typography>
                    )}
                  </Box>
                ) : (
                  `Erro: ${testResults[g.key].details?.error || 'Falha na conexao'}`
                )}
              </Alert>
            )}

            {/* Setup result */}
            {setupResult && (
              <Alert
                severity={setupResult.success ? 'success' : 'warning'}
                sx={{ mb: 2 }}
                onClose={() => setSetupResult(null)}
              >
                <Box>
                  <strong>{setupResult.message}</strong>
                  {setupResult.pgvector_version && (
                    <Typography variant="caption" display="block">
                      pgvector v{setupResult.pgvector_version}
                    </Typography>
                  )}
                  {setupResult.steps && setupResult.steps.length > 0 && (
                    <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                      {setupResult.steps.map((step: any, i: number) => (
                        <Box key={i} display="flex" alignItems="center" gap={0.5}>
                          {step.status === 'ok' || step.status === 'created' || step.status === 'already_exists' ? (
                            <CheckCircle sx={{ fontSize: 14, color: 'success.main' }} />
                          ) : step.status === 'skipped' ? (
                            <Info sx={{ fontSize: 14, color: 'text.secondary' }} />
                          ) : (
                            <Warning sx={{ fontSize: 14, color: 'error.main' }} />
                          )}
                          <Typography variant="caption">
                            {step.step}: {step.detail}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  )}
                  {setupResult.indexes_exist && setupResult.indexes_exist.length > 0 && (
                    <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                      Indices ativos: {setupResult.indexes_exist.join(', ')}
                    </Typography>
                  )}
                </Box>
              </Alert>
            )}

            {/* Provider fields */}
            <Grid container spacing={3}>
              {getGroupFields(g.key).map((field) => (
                <Grid item xs={12} md={6} key={field.key}>
                  <FieldWrapper
                    field={field}
                    overrideKeys={overrideKeys}
                    editedValues={editedValues}
                    onChange={onChange}
                  />
                </Grid>
              ))}
            </Grid>

            {/* Index management - only for pgvector */}
            {g.key === 'pgvector' && <IndexManager />}
          </Paper>
        ) : null
      )}

      {/* Save button */}
      {hasChanges && (
        <Box mt={3} display="flex" justifyContent="flex-end">
          <Button
            variant="contained"
            startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
            onClick={onSave}
            disabled={saving}
          >
            Salvar Alteracoes
          </Button>
        </Box>
      )}
    </>
  );
};

// Health tab with diagnostics integration
const HealthTab: React.FC<{
  health: HealthCheck | null;
  categories: SystemConfigCategory[];
  overrideCount: number;
}> = ({ health, categories, overrideCount }) => {
  const navigate = useNavigate();

  const StatusChip = ({ status }: { status?: string }) => {
    if (!status) return null;
    const isOk = status === 'ok' || status === 'healthy' || status === 'connected';
    return (
      <Chip
        icon={isOk ? <CheckCircle /> : <Warning />}
        label={status}
        size="small"
        color={isOk ? 'success' : 'warning'}
        variant="outlined"
      />
    );
  };

  const services = [
    { label: 'Banco de Dados', icon: <Storage fontSize="small" color="primary" />, status: health?.database },
    { label: 'Redis', icon: <Memory fontSize="small" color="primary" />, status: health?.redis },
    { label: 'Celery', icon: <SettingsIcon fontSize="small" color="primary" />, status: health?.celery },
    { label: 'Vector DB', icon: <Security fontSize="small" color="primary" />, status: health?.vector_db },
  ];

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Status dos Servicos
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
              {services.map((svc, i) => (
                <React.Fragment key={svc.label}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box display="flex" alignItems="center" gap={1}>
                      {svc.icon}
                      <Typography variant="body2">{svc.label}</Typography>
                    </Box>
                    <StatusChip status={svc.status} />
                  </Box>
                  {i < services.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </Box>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Informacoes do Sistema
            </Typography>
            <Box sx={{ mt: 2 }}>
              <Box display="flex" justifyContent="space-between" py={1}>
                <Typography variant="body2" color="text.secondary">Versao</Typography>
                <Typography variant="body2" fontWeight={600}>
                  {health?.version || '-'}
                </Typography>
              </Box>
              <Divider />
              <Box display="flex" justifyContent="space-between" py={1}>
                <Typography variant="body2" color="text.secondary">Status Geral</Typography>
                <StatusChip status={health?.status} />
              </Box>
              <Divider />
              <Box display="flex" justifyContent="space-between" py={1}>
                <Typography variant="body2" color="text.secondary">Categorias de Config</Typography>
                <Typography variant="body2" fontWeight={600}>{categories.length}</Typography>
              </Box>
              <Divider />
              <Box display="flex" justifyContent="space-between" py={1}>
                <Typography variant="body2" color="text.secondary">Overrides Ativos</Typography>
                <Typography variant="body2" fontWeight={600}>{overrideCount}</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12}>
        <Alert severity="info" action={
          <Button color="inherit" size="small" onClick={() => navigate('/diagnostics')}>
            Abrir Diagnostico
          </Button>
        }>
          Para testes detalhados de cada componente (PostgreSQL, Redis, OpenAI, Celery, Embeddings),
          visualizacao de logs e diagnostico completo do sistema, acesse a pagina de Diagnostico.
        </Alert>
      </Grid>
    </Grid>
  );
};


const SettingsPage: React.FC = () => {
  const { showSuccess, showError } = useNotification();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState(0);
  const [health, setHealth] = useState<HealthCheck | null>(null);

  // System config state
  const [config, setConfig] = useState<SystemConfigResponse | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, any>>({});
  const [hasChanges, setHasChanges] = useState(false);

  // Confirm dialogs
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [restartWarningOpen, setRestartWarningOpen] = useState(false);
  const [pendingSave, setPendingSave] = useState<Record<string, any> | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiService.getSystemConfig();
      setConfig(data);
      // Initialize edited values from current config
      const initial: Record<string, any> = {};
      data.categories.forEach((cat) => {
        cat.fields.forEach((field) => {
          initial[field.key] = field.value;
        });
      });
      setEditedValues(initial);
      setHasChanges(false);
    } catch (error) {
      showError('Erro ao carregar configuracoes do sistema');
    } finally {
      setLoading(false);
    }
  }, [showError]);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await apiService.healthCheck();
      setHealth(data);
    } catch (error) {
      console.error('Health check failed:', error);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchHealth();
  }, [fetchConfig, fetchHealth]);

  const handleFieldChange = (key: string, value: any) => {
    setEditedValues((prev) => {
      const next = { ...prev, [key]: value };

      // When llm_provider changes, auto-select a default model for the new provider
      if (key === 'llm_provider') {
        const defaultModels: Record<string, string> = {
          openai: 'gpt-4o',
          anthropic: 'claude-sonnet-4-20250514',
        };
        const currentModel = prev['chat_model'] || '';
        // Only reset if current model doesn't match the new provider
        const providerModels: Record<string, string[]> = {
          openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 'o3-mini'],
          anthropic: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
        };
        const validModels = providerModels[value] || [];
        if (!validModels.includes(currentModel)) {
          next['chat_model'] = defaultModels[value] || currentModel;
        }
      }

      return next;
    });
    setHasChanges(true);
  };

  const getChangedValues = (): Record<string, any> => {
    if (!config) return {};
    const changes: Record<string, any> = {};
    config.categories.forEach((cat) => {
      cat.fields.forEach((field) => {
        const original = field.value;
        const edited = editedValues[field.key];
        if (JSON.stringify(original) !== JSON.stringify(edited)) {
          changes[field.key] = edited;
        }
      });
    });
    return changes;
  };

  const hasRestartRequiredChanges = (): boolean => {
    if (!config) return false;
    const changes = getChangedValues();
    for (const key of Object.keys(changes)) {
      for (const cat of config.categories) {
        for (const field of cat.fields) {
          if (field.key === key && field.restart_required) {
            return true;
          }
        }
      }
    }
    return false;
  };

  const handleSave = async () => {
    const changes = getChangedValues();
    if (Object.keys(changes).length === 0) {
      showError('Nenhuma alteracao para salvar');
      return;
    }

    // Check if any changes require restart
    if (hasRestartRequiredChanges()) {
      setPendingSave(changes);
      setRestartWarningOpen(true);
      return;
    }

    await doSave(changes);
  };

  const doSave = async (values: Record<string, any>) => {
    try {
      setSaving(true);
      const result = await apiService.updateSystemConfig(values);
      showSuccess(
        `${result.updated_keys.length} configuracao(oes) atualizada(s)` +
        (result.restart_required ? '. Reinicie os servicos para aplicar todas as mudancas.' : '')
      );
      await fetchConfig();
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao salvar configuracoes');
    } finally {
      setSaving(false);
      setRestartWarningOpen(false);
      setPendingSave(null);
    }
  };

  const handleReset = async () => {
    try {
      await apiService.resetSystemConfig();
      showSuccess('Configuracoes restauradas aos valores padrao. Reinicie os servicos.');
      setResetDialogOpen(false);
      await fetchConfig();
    } catch (error) {
      showError('Erro ao restaurar configuracoes');
    }
  };

  if (loading) return <TableSkeleton />;

  const categories = config?.categories || [];
  // Last tab index is health
  const healthTabIndex = categories.length;

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Configuracoes do Sistema
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Todas as configuracoes do sistema podem ser ajustadas aqui
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          {hasChanges && (
            <Button
              variant="contained"
              color="primary"
              startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
              onClick={handleSave}
              disabled={saving}
            >
              Salvar Alteracoes
            </Button>
          )}
          {config?.has_overrides && (
            <Tooltip title="Restaurar todos os valores padrao">
              <Button
                variant="outlined"
                color="warning"
                startIcon={<RestartAlt />}
                onClick={() => setResetDialogOpen(true)}
              >
                Resetar
              </Button>
            </Tooltip>
          )}
          <Tooltip title="Atualizar">
            <IconButton onClick={() => { fetchConfig(); fetchHealth(); }}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Override indicator */}
      {config?.has_overrides && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {config.override_keys.length} configuracao(oes) personalizada(s) ativa(s).
          Estas sobrescrevem os valores do arquivo .env.
        </Alert>
      )}

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        {categories.map((cat) => (
          <Tab
            key={cat.category}
            label={cat.label}
            icon={iconMap[cat.icon] || <SettingsIcon />}
            iconPosition="start"
            sx={{ minHeight: 48 }}
          />
        ))}
        <Tab
          label="Saude do Sistema"
          icon={<Memory />}
          iconPosition="start"
          sx={{ minHeight: 48 }}
        />
      </Tabs>

      {/* Category Tabs */}
      {categories.map((cat, catIndex) => (
        tab === catIndex && (
          <Paper key={cat.category} sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
            <Box mb={3}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                {cat.label}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {cat.description}
              </Typography>
            </Box>

            {/* Grouped rendering for categories with groups (e.g., vector_db) */}
            {cat.groups && cat.groups.length > 0 ? (
              <GroupedCategoryRenderer
                category={cat}
                editedValues={editedValues}
                onChange={handleFieldChange}
                overrideKeys={config?.override_keys || []}
                hasChanges={hasChanges}
                saving={saving}
                onSave={handleSave}
              />
            ) : (
              <>
                {/* Flat rendering for regular categories */}
                <Grid container spacing={3}>
                  {cat.fields.map((field) => (
                    <Grid item xs={12} md={6} key={field.key}>
                      <FieldWrapper
                        field={field}
                        overrideKeys={config?.override_keys || []}
                        editedValues={editedValues}
                        onChange={handleFieldChange}
                      />
                    </Grid>
                  ))}
                </Grid>

                {/* Save button at bottom of each category */}
                {hasChanges && (
                  <Box mt={3} display="flex" justifyContent="flex-end">
                    <Button
                      variant="contained"
                      startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
                      onClick={handleSave}
                      disabled={saving}
                    >
                      Salvar Alteracoes
                    </Button>
                  </Box>
                )}
              </>
            )}
          </Paper>
        )
      ))}

      {/* Health Tab */}
      {tab === healthTabIndex && (
        <HealthTab health={health} categories={categories} overrideCount={config?.override_keys.length || 0} />
      )}

      {/* Restart Warning Dialog */}
      <Dialog
        open={restartWarningOpen}
        onClose={() => setRestartWarningOpen(false)}
      >
        <DialogTitle fontWeight={600}>
          Reinicio Necessario
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Algumas configuracoes alteradas requerem reiniciar os servicos Docker para entrarem em vigor.
          </Alert>
          <Typography variant="body2">
            Apos salvar, execute no servidor:
          </Typography>
          <Box
            sx={{
              mt: 1,
              p: 1.5,
              bgcolor: 'grey.100',
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.85rem',
            }}
          >
            docker compose -f docker-compose.prod.yml restart api celery-worker
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setRestartWarningOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => pendingSave && doSave(pendingSave)}
            disabled={saving}
            startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <Save />}
          >
            Salvar Mesmo Assim
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reset Confirmation Dialog */}
      <Dialog open={resetDialogOpen} onClose={() => setResetDialogOpen(false)}>
        <DialogTitle fontWeight={600}>
          Restaurar Configuracoes Padrao
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Isso vai remover TODAS as personalizacoes feitas pelo frontend,
            voltando aos valores definidos no arquivo .env e nos padroes do sistema.
          </Alert>
          <Typography variant="body2">
            Esta acao requer reiniciar os servicos para ter efeito completo.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setResetDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={handleReset}
            startIcon={<RestartAlt />}
          >
            Restaurar Padroes
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SettingsPage;
