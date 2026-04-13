import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Paper,
  Typography,
  Button,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Autocomplete,
  TextField,
  Chip,
  Grid,
  Card,
  CardContent,
  useTheme,
  alpha,
  IconButton,
  Tooltip,
  Tabs,
  Tab,
  Divider,
  Alert,
  Switch,
  FormControlLabel,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  Collapse,
} from '@mui/material';
import {
  CloudUpload,
  Description,
  CheckCircle,
  Error as ErrorIcon,
  HourglassEmpty,
  Sync,
  Delete,
  PictureAsPdf,
  Article,
  Image,
  FolderOpen,
  Search as SearchIcon,
  PlayArrow,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { websocketService } from '../services/websocket';
import { Candidate, WebSocketMessage } from '../types';
import { useNotification } from '../contexts/NotificationContext';

interface UploadFile {
  file: File;
  documentId?: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  message: string;
}

interface ScanResult {
  folder_path: string;
  exists: boolean;
  readable: boolean;
  total_files: number;
  supported_files: number;
  unsupported_files: number;
  already_imported: number;
  files: any[];
  summary_by_extension: Record<string, number>;
  total_size_mb: number;
}

interface ImportResult {
  folder_path: string;
  total_files: number;
  imported: number;
  skipped_duplicates: number;
  errors: number;
  results: any[];
}

const getFileIcon = (mimeType: string) => {
  if (mimeType.includes('pdf')) return <PictureAsPdf color="error" />;
  if (mimeType.includes('image')) return <Image color="primary" />;
  return <Article color="action" />;
};

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const UploadPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [tabValue, setTabValue] = useState(0);

  // ===== Individual Upload State =====
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);

  // ===== Batch Import State =====
  const [folderPath, setFolderPath] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [showImportDetails, setShowImportDetails] = useState(false);

  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        const data = await apiService.getCandidates();
        setCandidates(data);
      } catch (error) {
        console.error('Error fetching candidates:', error);
      }
    };
    fetchCandidates();

    const handleProgress = (message: WebSocketMessage) => {
      if (message.type === 'document_progress' && message.document_id) {
        setFiles((prevFiles) =>
          prevFiles.map((f) =>
            f.documentId === message.document_id
              ? {
                  ...f,
                  status: (message.status as any) || f.status,
                  progress: message.progress || f.progress,
                  message: message.message || f.message,
                }
              : f
          )
        );
      }
    };

    websocketService.on('document_progress', handleProgress);
    return () => {
      websocketService.off('document_progress', handleProgress);
    };
  }, []);

  // ===== Individual Upload Handlers =====
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const newFiles: UploadFile[] = acceptedFiles.map((file) => ({
        file,
        status: 'pending',
        progress: 0,
        message: 'Aguardando upload',
      }));

      setFiles((prev) => [...prev, ...newFiles]);

      for (const uploadFile of newFiles) {
        try {
          setFiles((prev) =>
            prev.map((f) =>
              f.file === uploadFile.file
                ? { ...f, status: 'uploading', message: 'Fazendo upload...' }
                : f
            )
          );

          const document = await apiService.uploadDocument(
            uploadFile.file,
            selectedCandidate?.id
          );

          setFiles((prev) =>
            prev.map((f) =>
              f.file === uploadFile.file
                ? {
                    ...f,
                    documentId: document.id,
                    status: 'processing',
                    progress: 0,
                    message: 'Processando documento...',
                  }
                : f
            )
          );

          websocketService.subscribeDocument(document.id);
          showSuccess(`${uploadFile.file.name} enviado com sucesso`);
        } catch (err: any) {
          setFiles((prev) =>
            prev.map((f) =>
              f.file === uploadFile.file
                ? {
                    ...f,
                    status: 'error',
                    message: err.response?.data?.detail || 'Erro no upload',
                  }
                : f
            )
          );
          showError(`Erro ao enviar ${uploadFile.file.name}`);
        }
      }
    },
    [selectedCandidate, showSuccess, showError]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt'],
      'application/rtf': ['.rtf'],
      'image/*': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp'],
    },
    maxSize: 20 * 1024 * 1024,
  });

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'completed':
        return { icon: <CheckCircle color="success" />, color: 'success.main' };
      case 'error':
        return { icon: <ErrorIcon color="error" />, color: 'error.main' };
      case 'uploading':
        return { icon: <CloudUpload color="primary" />, color: 'primary.main' };
      case 'processing':
        return { icon: <Sync color="info" sx={{ animation: 'spin 1s linear infinite', '@keyframes spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } } }} />, color: 'info.main' };
      default:
        return { icon: <HourglassEmpty color="action" />, color: 'text.secondary' };
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const clearCompleted = () => {
    setFiles((prev) => prev.filter((f) => f.status !== 'completed' && f.status !== 'error'));
  };

  const completedCount = files.filter((f) => f.status === 'completed').length;
  const errorCount = files.filter((f) => f.status === 'error').length;

  // ===== Batch Import Handlers =====
  const handleScanFolder = async () => {
    if (!folderPath.trim()) {
      showError('Informe o caminho da pasta');
      return;
    }

    setScanning(true);
    setScanResult(null);
    setImportResult(null);

    try {
      const result = await apiService.batchImportScan(folderPath, recursive);
      setScanResult(result);
      showSuccess(`Pasta escaneada: ${result.supported_files} arquivos encontrados`);
    } catch (err: any) {
      showError(err.response?.data?.detail || 'Erro ao escanear pasta');
    } finally {
      setScanning(false);
    }
  };

  const handleBatchImport = async () => {
    if (!folderPath.trim()) {
      showError('Informe o caminho da pasta');
      return;
    }

    setImporting(true);
    setImportResult(null);

    try {
      const result = await apiService.batchImportExecute(
        folderPath,
        recursive,
        skipDuplicates,
        undefined,
        selectedCandidate?.id
      );
      setImportResult(result);
      showSuccess(
        `Importacao concluida: ${result.imported} importados, ${result.skipped_duplicates} duplicados`
      );
    } catch (err: any) {
      showError(err.response?.data?.detail || 'Erro na importacao em lote');
    } finally {
      setImporting(false);
    }
  };

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Upload de Curriculos
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Envie curriculos individualmente ou importe em lote de uma pasta do servidor.
      </Typography>

      <Paper sx={{ mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Tabs
          value={tabValue}
          onChange={(_, v) => setTabValue(v)}
          sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 2 }}
        >
          <Tab icon={<CloudUpload />} iconPosition="start" label="Upload Individual" />
          <Tab icon={<FolderOpen />} iconPosition="start" label="Importar da Pasta" />
        </Tabs>

        {/* ===== TAB 1: Individual Upload ===== */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ px: 3, pb: 3 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={8}>
                {/* Candidate Selection */}
                <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
                  <Autocomplete
                    options={candidates}
                    getOptionLabel={(option) => `${option.full_name} ${option.email ? `(${option.email})` : ''}`}
                    value={selectedCandidate}
                    onChange={(_, newValue) => setSelectedCandidate(newValue)}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Vincular a candidato (opcional)"
                        helperText="Deixe em branco para criar um novo candidato automaticamente"
                      />
                    )}
                  />
                </Paper>

                {/* Drop Zone */}
                <Paper
                  {...getRootProps()}
                  sx={{
                    p: 6,
                    textAlign: 'center',
                    border: '2px dashed',
                    borderColor: isDragActive ? 'primary.main' : 'divider',
                    bgcolor: isDragActive
                      ? alpha(theme.palette.primary.main, 0.06)
                      : 'background.paper',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    borderRadius: 3,
                    mb: 3,
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: alpha(theme.palette.primary.main, 0.04),
                    },
                  }}
                >
                  <input {...getInputProps()} />
                  <CloudUpload sx={{ fontSize: 64, color: 'primary.main', mb: 2, opacity: 0.8 }} />
                  {isDragActive ? (
                    <Typography variant="h6" color="primary">
                      Solte os arquivos aqui...
                    </Typography>
                  ) : (
                    <>
                      <Typography variant="h6" fontWeight={600} gutterBottom>
                        Arraste arquivos aqui ou clique para selecionar
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Tamanho maximo: 20MB por arquivo
                      </Typography>
                      <Box display="flex" justifyContent="center" gap={1} flexWrap="wrap">
                        {['PDF', 'DOCX', 'DOC', 'TXT', 'RTF', 'JPG', 'PNG', 'BMP', 'TIFF', 'WEBP'].map((fmt) => (
                          <Chip key={fmt} label={fmt} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </>
                  )}
                </Paper>
              </Grid>

              {/* Info sidebar */}
              <Grid item xs={12} md={4}>
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" fontWeight={600} gutterBottom>
                      Como funciona
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                      {[
                        { step: '1', text: 'Faca o upload do curriculo' },
                        { step: '2', text: 'O sistema extrai o texto (OCR se necessario)' },
                        { step: '3', text: 'Dados sao estruturados automaticamente' },
                        { step: '4', text: 'Embeddings sao gerados para busca' },
                      ].map((item) => (
                        <Box key={item.step} display="flex" gap={1.5} alignItems="center">
                          <Chip
                            label={item.step}
                            size="small"
                            color="primary"
                            sx={{ fontWeight: 700, minWidth: 28 }}
                          />
                          <Typography variant="body2">{item.text}</Typography>
                        </Box>
                      ))}
                    </Box>
                  </CardContent>
                </Card>

                {files.length > 0 && (
                  <Card>
                    <CardContent>
                      <Typography variant="h6" fontWeight={600} gutterBottom>
                        Status
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        <Chip label={`${files.length} total`} size="small" />
                        {completedCount > 0 && (
                          <Chip label={`${completedCount} concluido(s)`} size="small" color="success" />
                        )}
                        {errorCount > 0 && (
                          <Chip label={`${errorCount} erro(s)`} size="small" color="error" />
                        )}
                      </Box>
                    </CardContent>
                  </Card>
                )}
              </Grid>
            </Grid>

            {/* File List */}
            {files.length > 0 && (
              <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6" fontWeight={600}>
                    Arquivos ({files.length})
                  </Typography>
                  <Button onClick={clearCompleted} size="small" variant="outlined">
                    Limpar finalizados
                  </Button>
                </Box>

                <List disablePadding>
                  {files.map((uploadFile, index) => {
                    const statusInfo = getStatusInfo(uploadFile.status);
                    return (
                      <ListItem
                        key={index}
                        sx={{
                          borderRadius: 1.5,
                          mb: 1,
                          border: '1px solid',
                          borderColor: 'divider',
                        }}
                        secondaryAction={
                          <Tooltip title="Remover">
                            <IconButton size="small" onClick={() => removeFile(index)}>
                              <Delete fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        }
                      >
                        <ListItemIcon>{statusInfo.icon}</ListItemIcon>
                        <ListItemText
                          primary={
                            <Typography variant="body2" fontWeight={500}>
                              {uploadFile.file.name}
                            </Typography>
                          }
                          secondary={
                            <Box>
                              <Typography variant="caption" color="text.secondary">
                                {uploadFile.message} - {(uploadFile.file.size / 1024).toFixed(0)} KB
                              </Typography>
                              {(uploadFile.status === 'uploading' || uploadFile.status === 'processing') && (
                                <LinearProgress
                                  variant={uploadFile.progress > 0 ? 'determinate' : 'indeterminate'}
                                  value={uploadFile.progress}
                                  sx={{ mt: 0.5, borderRadius: 1 }}
                                />
                              )}
                            </Box>
                          }
                        />
                      </ListItem>
                    );
                  })}
                </List>
              </Paper>
            )}
          </Box>
        </TabPanel>

        {/* ===== TAB 2: Batch Import ===== */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ px: 3, pb: 3 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              Importe curriculos em lote a partir de uma pasta no servidor. O sistema escaneia a pasta,
              detecta arquivos suportados (PDF, DOCX, TXT, imagens), verifica duplicatas e processa
              todos automaticamente com OCR e extracao de dados.
            </Alert>

            <Grid container spacing={3}>
              <Grid item xs={12} md={8}>
                <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Caminho da Pasta
                  </Typography>

                  <TextField
                    fullWidth
                    label="Caminho da pasta no servidor"
                    placeholder="/home/user/curriculos ou /mnt/rede/rh/curriculos"
                    value={folderPath}
                    onChange={(e) => setFolderPath(e.target.value)}
                    sx={{ mb: 2 }}
                    helperText="Caminho absoluto da pasta no servidor onde estao os curriculos"
                  />

                  <Box display="flex" gap={2} flexWrap="wrap" mb={2}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={recursive}
                          onChange={(e) => setRecursive(e.target.checked)}
                        />
                      }
                      label="Incluir subpastas"
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          checked={skipDuplicates}
                          onChange={(e) => setSkipDuplicates(e.target.checked)}
                        />
                      }
                      label="Pular duplicados"
                    />
                  </Box>

                  <Autocomplete
                    options={candidates}
                    getOptionLabel={(option) => `${option.full_name} ${option.email ? `(${option.email})` : ''}`}
                    value={selectedCandidate}
                    onChange={(_, newValue) => setSelectedCandidate(newValue)}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Vincular todos a um candidato (opcional)"
                        helperText="Deixe em branco para criar um candidato por arquivo"
                        size="small"
                      />
                    )}
                    sx={{ mb: 3 }}
                  />

                  <Box display="flex" gap={2}>
                    <Button
                      variant="outlined"
                      startIcon={scanning ? <CircularProgress size={18} /> : <SearchIcon />}
                      onClick={handleScanFolder}
                      disabled={scanning || importing || !folderPath.trim()}
                    >
                      {scanning ? 'Escaneando...' : 'Escanear Pasta'}
                    </Button>

                    <Button
                      variant="contained"
                      startIcon={importing ? <CircularProgress size={18} color="inherit" /> : <PlayArrow />}
                      onClick={handleBatchImport}
                      disabled={importing || scanning || !folderPath.trim()}
                      color="primary"
                    >
                      {importing ? 'Importando...' : 'Importar Tudo'}
                    </Button>
                  </Box>
                </Paper>

                {/* Scan Results */}
                {scanResult && (
                  <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                      Resultado do Scan
                    </Typography>

                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center" p={1}>
                          <Typography variant="h5" fontWeight={700} color="primary">
                            {scanResult.supported_files}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Suportados
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center" p={1}>
                          <Typography variant="h5" fontWeight={700} color="warning.main">
                            {scanResult.already_imported}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Ja importados
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center" p={1}>
                          <Typography variant="h5" fontWeight={700} color="text.secondary">
                            {scanResult.unsupported_files}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Nao suportados
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center" p={1}>
                          <Typography variant="h5" fontWeight={700}>
                            {scanResult.total_size_mb.toFixed(1)} MB
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Tamanho total
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>

                    <Divider sx={{ mb: 2 }} />

                    <Typography variant="body2" fontWeight={600} gutterBottom>
                      Por extensao:
                    </Typography>
                    <Box display="flex" gap={1} flexWrap="wrap" mb={2}>
                      {Object.entries(scanResult.summary_by_extension).map(([ext, count]) => (
                        <Chip
                          key={ext}
                          label={`${ext}: ${count}`}
                          size="small"
                          variant="outlined"
                          color="primary"
                        />
                      ))}
                    </Box>

                    {scanResult.files.length > 0 && (
                      <>
                        <Typography variant="body2" fontWeight={600} gutterBottom>
                          Arquivos encontrados ({scanResult.files.length}):
                        </Typography>
                        <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Arquivo</TableCell>
                                <TableCell>Tipo</TableCell>
                                <TableCell align="right">Tamanho</TableCell>
                                <TableCell>Status</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {scanResult.files.map((file: any, idx: number) => (
                                <TableRow key={idx}>
                                  <TableCell>
                                    <Typography variant="caption" noWrap sx={{ maxWidth: 250, display: 'block' }}>
                                      {file.name}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>
                                    <Chip label={file.extension} size="small" />
                                  </TableCell>
                                  <TableCell align="right">
                                    <Typography variant="caption">
                                      {file.size_mb > 1 ? `${file.size_mb} MB` : `${(file.size_bytes / 1024).toFixed(0)} KB`}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>
                                    {file.already_imported ? (
                                      <Chip label="Ja importado" size="small" color="warning" variant="outlined" />
                                    ) : (
                                      <Chip label="Novo" size="small" color="success" variant="outlined" />
                                    )}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </Box>
                      </>
                    )}
                  </Paper>
                )}

                {/* Import Results */}
                {importResult && (
                  <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                      Resultado da Importacao
                    </Typography>

                    <Alert
                      severity={importResult.errors > 0 ? 'warning' : 'success'}
                      sx={{ mb: 2 }}
                    >
                      {importResult.imported} importados, {importResult.skipped_duplicates} duplicados
                      {importResult.errors > 0 && `, ${importResult.errors} erros`}
                    </Alert>

                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      <Grid item xs={4}>
                        <Box textAlign="center">
                          <Typography variant="h5" fontWeight={700} color="success.main">
                            {importResult.imported}
                          </Typography>
                          <Typography variant="caption">Importados</Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={4}>
                        <Box textAlign="center">
                          <Typography variant="h5" fontWeight={700} color="warning.main">
                            {importResult.skipped_duplicates}
                          </Typography>
                          <Typography variant="caption">Duplicados</Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={4}>
                        <Box textAlign="center">
                          <Typography variant="h5" fontWeight={700} color="error.main">
                            {importResult.errors}
                          </Typography>
                          <Typography variant="caption">Erros</Typography>
                        </Box>
                      </Grid>
                    </Grid>

                    <Button
                      size="small"
                      onClick={() => setShowImportDetails(!showImportDetails)}
                      endIcon={showImportDetails ? <ExpandLess /> : <ExpandMore />}
                    >
                      {showImportDetails ? 'Ocultar detalhes' : 'Ver detalhes'}
                    </Button>

                    <Collapse in={showImportDetails}>
                      <Box sx={{ maxHeight: 300, overflow: 'auto', mt: 2 }}>
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Arquivo</TableCell>
                              <TableCell>Status</TableCell>
                              <TableCell>Mensagem</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {importResult.results.map((r: any, idx: number) => (
                              <TableRow key={idx}>
                                <TableCell>
                                  <Typography variant="caption" noWrap sx={{ maxWidth: 200, display: 'block' }}>
                                    {r.filename}
                                  </Typography>
                                </TableCell>
                                <TableCell>
                                  <Chip
                                    label={r.status}
                                    size="small"
                                    color={
                                      r.status === 'imported'
                                        ? 'success'
                                        : r.status === 'skipped_duplicate'
                                        ? 'warning'
                                        : 'error'
                                    }
                                    variant="outlined"
                                  />
                                </TableCell>
                                <TableCell>
                                  <Typography variant="caption">{r.message}</Typography>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </Box>
                    </Collapse>
                  </Paper>
                )}
              </Grid>

              {/* Batch Import Sidebar */}
              <Grid item xs={12} md={4}>
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" fontWeight={600} gutterBottom>
                      Importacao em Lote
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                      {[
                        { step: '1', text: 'Informe o caminho da pasta no servidor' },
                        { step: '2', text: 'Escaneie para ver os arquivos disponiveis' },
                        { step: '3', text: 'Clique em Importar para processar tudo' },
                        { step: '4', text: 'Cada arquivo e processado com OCR automatico' },
                      ].map((item) => (
                        <Box key={item.step} display="flex" gap={1.5} alignItems="center">
                          <Chip
                            label={item.step}
                            size="small"
                            color="primary"
                            sx={{ fontWeight: 700, minWidth: 28 }}
                          />
                          <Typography variant="body2">{item.text}</Typography>
                        </Box>
                      ))}
                    </Box>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                      Formatos suportados
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap">
                      {['PDF', 'DOC', 'DOCX', 'TXT', 'RTF', 'ODT', 'JPG', 'PNG', 'GIF', 'BMP', 'TIFF'].map(
                        (fmt) => (
                          <Chip key={fmt} label={fmt} size="small" variant="outlined" />
                        )
                      )}
                    </Box>

                    <Typography variant="subtitle2" fontWeight={600} sx={{ mt: 2 }} gutterBottom>
                      Exemplos de caminhos
                    </Typography>
                    <Typography variant="caption" color="text.secondary" component="div">
                      /home/user/curriculos<br />
                      /mnt/rede/rh/curriculos<br />
                      /mnt/gdrive/Curriculos<br />
                      /app/uploads/pendentes
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default UploadPage;
