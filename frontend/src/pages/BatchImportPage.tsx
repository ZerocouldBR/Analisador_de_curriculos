import React, { useState, useEffect, useCallback } from 'react';
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
  TextField,
  FormControlLabel,
  Checkbox,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  FolderOpen,
  Search,
  CloudUpload,
  CheckCircle,
  Warning,
  Error as ErrorIcon,
  Info,
  Description,
  Refresh,
  History,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';

const BatchImportPage: React.FC = () => {
  const { showSuccess, showError } = useNotification();

  // Scan state
  const [folderPath, setFolderPath] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<any>(null);

  // Validation state
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);

  // Import state
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

  // History state
  const [history, setHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const fetchHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const data = await apiService.getImportHistory(20);
      setHistory(data || []);
    } catch (e: any) {
      console.error('Erro ao carregar historico:', e);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleValidatePath = async () => {
    if (!folderPath.trim()) {
      showError('Informe o caminho da pasta');
      return;
    }
    setValidating(true);
    setValidationResult(null);
    try {
      const result = await apiService.validateFolderPath(folderPath.trim());
      setValidationResult(result);
    } catch (e: any) {
      showError(e.response?.data?.detail || 'Erro ao validar caminho');
    } finally {
      setValidating(false);
    }
  };

  const handleScan = async () => {
    if (!folderPath.trim()) {
      showError('Informe o caminho da pasta');
      return;
    }
    setScanning(true);
    setScanResult(null);
    setImportResult(null);
    try {
      const result = await apiService.scanFolder({
        folder_path: folderPath.trim(),
        recursive,
      });
      setScanResult(result);
    } catch (e: any) {
      showError(e.response?.data?.detail || 'Erro ao escanear pasta');
    } finally {
      setScanning(false);
    }
  };

  const handleImport = async () => {
    if (!folderPath.trim()) return;
    setImporting(true);
    setImportResult(null);
    try {
      const result = await apiService.batchImport({
        folder_path: folderPath.trim(),
        recursive,
        skip_duplicates: skipDuplicates,
      });
      setImportResult(result);
      if (result.imported > 0) {
        showSuccess(`${result.imported} arquivo(s) importado(s) com sucesso!`);
      }
      fetchHistory();
    } catch (e: any) {
      showError(e.response?.data?.detail || 'Erro na importacao');
    } finally {
      setImporting(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'imported': return <CheckCircle sx={{ color: 'success.main', fontSize: 18 }} />;
      case 'skipped_duplicate': return <Info sx={{ color: 'info.main', fontSize: 18 }} />;
      case 'error': return <ErrorIcon sx={{ color: 'error.main', fontSize: 18 }} />;
      default: return <Info sx={{ fontSize: 18 }} />;
    }
  };

  return (
    <Box className="fade-in">
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Importacao em Lote
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Importe curriculos de pastas locais, rede (SMB/NFS) ou drives montados
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={showHistory ? <ExpandLess /> : <History />}
          onClick={() => setShowHistory(!showHistory)}
        >
          {showHistory ? 'Ocultar Historico' : 'Historico'}
        </Button>
      </Box>

      {/* History panel */}
      <Collapse in={showHistory}>
        <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6" fontWeight={600}>Historico de Importacoes</Typography>
            <IconButton onClick={fetchHistory} disabled={loadingHistory}>
              {loadingHistory ? <CircularProgress size={20} /> : <Refresh />}
            </IconButton>
          </Box>
          {history.length === 0 ? (
            <Typography variant="body2" color="text.secondary">Nenhuma importacao realizada</Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {history.filter(h => h.action === 'batch_import_completed').map((h) => (
                <Paper key={h.id} variant="outlined" sx={{ p: 1.5 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box>
                      <Typography variant="body2" fontWeight={600}>
                        {h.metadata?.folder || 'Pasta desconhecida'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {h.created_at ? new Date(h.created_at).toLocaleString() : '-'}
                      </Typography>
                    </Box>
                    <Box display="flex" gap={0.5}>
                      {h.metadata?.imported > 0 && (
                        <Chip label={`${h.metadata.imported} importados`} size="small" color="success" variant="outlined" sx={{ fontSize: '0.65rem', height: 20 }} />
                      )}
                      {h.metadata?.skipped > 0 && (
                        <Chip label={`${h.metadata.skipped} pulados`} size="small" color="info" variant="outlined" sx={{ fontSize: '0.65rem', height: 20 }} />
                      )}
                      {h.metadata?.errors > 0 && (
                        <Chip label={`${h.metadata.errors} erros`} size="small" color="error" variant="outlined" sx={{ fontSize: '0.65rem', height: 20 }} />
                      )}
                    </Box>
                  </Box>
                </Paper>
              ))}
            </Box>
          )}
        </Paper>
      </Collapse>

      {/* Input section */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Selecionar Pasta
        </Typography>

        <Grid container spacing={2} alignItems="flex-end">
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Caminho da Pasta"
              value={folderPath}
              onChange={(e) => {
                setFolderPath(e.target.value);
                setScanResult(null);
                setImportResult(null);
                setValidationResult(null);
              }}
              placeholder="/mnt/rh/curriculos"
              helperText="Pasta local, rede montada (SMB/NFS) ou drive compartilhado"
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <Box display="flex" gap={1} flexWrap="wrap">
              <Button
                variant="outlined"
                onClick={handleValidatePath}
                disabled={validating || !folderPath.trim()}
                startIcon={validating ? <CircularProgress size={16} /> : <FolderOpen />}
              >
                Validar Caminho
              </Button>
              <Button
                variant="contained"
                onClick={handleScan}
                disabled={scanning || !folderPath.trim()}
                startIcon={scanning ? <CircularProgress size={16} color="inherit" /> : <Search />}
              >
                Escanear Pasta
              </Button>
            </Box>
          </Grid>
        </Grid>

        <Box display="flex" gap={3} mt={2}>
          <FormControlLabel
            control={<Switch checked={recursive} onChange={(e) => setRecursive(e.target.checked)} />}
            label={
              <Box>
                <Typography variant="body2">Recursivo</Typography>
                <Typography variant="caption" color="text.secondary">Incluir subpastas</Typography>
              </Box>
            }
          />
          <FormControlLabel
            control={<Switch checked={skipDuplicates} onChange={(e) => setSkipDuplicates(e.target.checked)} />}
            label={
              <Box>
                <Typography variant="body2">Pular duplicatas</Typography>
                <Typography variant="caption" color="text.secondary">Verificar hash SHA256</Typography>
              </Box>
            }
          />
        </Box>

        {/* Validation result */}
        {validationResult && (
          <Alert
            severity={validationResult.exists && validationResult.is_readable ? 'success' : 'warning'}
            sx={{ mt: 2 }}
            onClose={() => setValidationResult(null)}
          >
            <Box>
              <strong>{validationResult.exists ? 'Pasta acessivel' : 'Pasta nao encontrada'}</strong>
              {validationResult.exists && (
                <Typography variant="caption" display="block">
                  Leitura: {validationResult.is_readable ? 'Sim' : 'Nao'} |
                  Escrita: {validationResult.is_writable ? 'Sim' : 'Nao'}
                  {validationResult.disk_free_gb !== undefined && ` | Disco livre: ${validationResult.disk_free_gb} GB`}
                  {validationResult.file_count !== undefined && ` | ${validationResult.file_count} arquivo(s), ${validationResult.directory_count} pasta(s)`}
                </Typography>
              )}
              {validationResult.suggestions && (
                <Box sx={{ mt: 1 }}>
                  {validationResult.suggestions.map((s: string, i: number) => (
                    <Typography key={i} variant="caption" display="block" sx={{ fontFamily: 'monospace' }}>
                      {s}
                    </Typography>
                  ))}
                </Box>
              )}
            </Box>
          </Alert>
        )}
      </Paper>

      {/* Scan results */}
      {scanResult && (
        <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6" fontWeight={600}>
              Resultado do Escaneamento
            </Typography>
            <Button
              variant="contained"
              color="success"
              size="large"
              onClick={handleImport}
              disabled={importing || scanResult.supported_files === 0}
              startIcon={importing ? <CircularProgress size={18} color="inherit" /> : <CloudUpload />}
            >
              {importing ? 'Importando...' : `Importar ${scanResult.supported_files - scanResult.already_imported} arquivo(s)`}
            </Button>
          </Box>

          {/* Stats cards */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={6} sm={3}>
              <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 1.5 }}>
                  <Typography variant="h5" fontWeight={700} color="primary">{scanResult.total_files}</Typography>
                  <Typography variant="caption">Total de arquivos</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 1.5 }}>
                  <Typography variant="h5" fontWeight={700} color="success.main">{scanResult.supported_files}</Typography>
                  <Typography variant="caption">Suportados</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 1.5 }}>
                  <Typography variant="h5" fontWeight={700} color="info.main">{scanResult.already_imported}</Typography>
                  <Typography variant="caption">Ja importados</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 1.5 }}>
                  <Typography variant="h5" fontWeight={700}>{scanResult.total_size_mb} MB</Typography>
                  <Typography variant="caption">Tamanho total</Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Extension summary */}
          {scanResult.summary_by_extension && Object.keys(scanResult.summary_by_extension).length > 0 && (
            <Box display="flex" gap={0.5} flexWrap="wrap" mb={2}>
              {Object.entries(scanResult.summary_by_extension).map(([ext, count]) => (
                <Chip key={ext} label={`${ext}: ${count}`} size="small" variant="outlined" />
              ))}
            </Box>
          )}

          {/* File list */}
          {scanResult.files && scanResult.files.length > 0 && (
            <TableContainer sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Arquivo</TableCell>
                    <TableCell>Extensao</TableCell>
                    <TableCell align="right">Tamanho</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {scanResult.files.map((file: any, i: number) => (
                    <TableRow key={i} sx={{ opacity: file.already_imported ? 0.5 : 1 }}>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={0.5}>
                          <Description fontSize="small" color="action" />
                          <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>{file.name}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip label={file.extension} size="small" sx={{ fontSize: '0.65rem', height: 18 }} />
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="caption">{file.size_mb} MB</Typography>
                      </TableCell>
                      <TableCell>
                        {file.already_imported ? (
                          <Chip label="Ja importado" size="small" color="info" variant="outlined" sx={{ fontSize: '0.65rem', height: 18 }} />
                        ) : (
                          <Chip label="Novo" size="small" color="success" variant="outlined" sx={{ fontSize: '0.65rem', height: 18 }} />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      )}

      {/* Import results */}
      {importResult && (
        <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="h6" fontWeight={600} gutterBottom>
            Resultado da Importacao
          </Typography>

          <Alert
            severity={importResult.errors > 0 ? 'warning' : 'success'}
            sx={{ mb: 2 }}
          >
            {importResult.imported} importado(s), {importResult.skipped_duplicates} duplicata(s) pulada(s), {importResult.errors} erro(s)
          </Alert>

          {importResult.results && importResult.results.length > 0 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, maxHeight: 300, overflow: 'auto' }}>
              {importResult.results.map((r: any, i: number) => (
                <Box key={i} display="flex" alignItems="center" gap={1} sx={{ p: 0.5 }}>
                  {getStatusIcon(r.status)}
                  <Typography variant="body2" sx={{ flex: 1, fontSize: '0.8rem' }}>{r.filename}</Typography>
                  <Typography variant="caption" color="text.secondary">{r.message}</Typography>
                </Box>
              ))}
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
};

export default BatchImportPage;
