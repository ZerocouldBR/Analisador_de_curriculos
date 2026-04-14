import React, { useState, useCallback, useEffect, useRef } from 'react';
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
  Alert,
} from '@mui/material';
import {
  CloudUpload,
  CheckCircle,
  Error as ErrorIcon,
  HourglassEmpty,
  Sync,
  Delete,
  PictureAsPdf,
  Article,
  Image,
  FolderOpen,
  UploadFile as UploadFileIcon,
  DriveFolderUpload,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { websocketService } from '../services/websocket';
import { Candidate, WebSocketMessage } from '../types';
import { useNotification } from '../contexts/NotificationContext';

let uploadIdCounter = 0;

interface UploadFile {
  id: number; // Unique ID to avoid filename collision
  file: File;
  documentId?: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  message: string;
}

const getFileIcon = (mimeType: string) => {
  if (mimeType.includes('pdf')) return <PictureAsPdf color="error" />;
  if (mimeType.includes('image')) return <Image color="primary" />;
  return <Article color="action" />;
};

const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.rtf', '.odt', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'];

const isSupportedFile = (file: File): boolean => {
  const parts = file.name.split('.');
  if (parts.length < 2) return false; // No extension
  const ext = '.' + (parts.pop()?.toLowerCase() || '');
  return SUPPORTED_EXTENSIONS.includes(ext);
};

const UploadPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError, showInfo } = useNotification();
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkProgress, setBulkProgress] = useState({ current: 0, total: 0 });
  const folderInputRef = useRef<HTMLInputElement>(null);

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

  // Upload individual files sequentially
  const uploadFilesSequentially = useCallback(
    async (acceptedFiles: File[]) => {
      const newFiles: UploadFile[] = acceptedFiles.map((file) => ({
        id: ++uploadIdCounter,
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
              f.id === uploadFile.id
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
              f.id === uploadFile.id
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
              f.id === uploadFile.id
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

  // Bulk upload using the bulk endpoint
  const uploadFilesBulk = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      setBulkUploading(true);
      setBulkProgress({ current: 0, total: acceptedFiles.length });

      const newFiles: UploadFile[] = acceptedFiles.map((file) => ({
        id: ++uploadIdCounter,
        file,
        status: 'uploading',
        progress: 0,
        message: 'Aguardando upload em lote...',
      }));

      setFiles((prev) => [...prev, ...newFiles]);

      // Upload in batches of 10
      const batchSize = 10;
      let totalUploaded = 0;
      let totalErrors = 0;

      for (let i = 0; i < acceptedFiles.length; i += batchSize) {
        const batch = acceptedFiles.slice(i, i + batchSize);
        // Map batch files to their UploadFile entries for proper matching
        const batchUploadFiles = newFiles.slice(i, i + batchSize);

        try {
          const result = await apiService.bulkUploadDocuments(
            batch,
            selectedCandidate?.id
          );

          // Update individual file statuses - match by index within batch
          result.results.forEach((fileResult: any, resultIdx: number) => {
            const matchedUpload = batchUploadFiles[resultIdx];
            if (!matchedUpload) return;

            setFiles((prev) =>
              prev.map((f) => {
                if (f.id !== matchedUpload.id) return f;
                if (fileResult.status === 'uploaded') {
                  if (fileResult.document_id) {
                    websocketService.subscribeDocument(fileResult.document_id);
                  }
                  return {
                    ...f,
                    documentId: fileResult.document_id,
                    status: 'processing',
                    progress: 0,
                    message: 'Processando documento...',
                  };
                } else {
                  return {
                    ...f,
                    status: 'error',
                    message: fileResult.message,
                  };
                }
              })
            );
          });

          totalUploaded += result.uploaded;
          totalErrors += result.errors;
        } catch (err: any) {
          // Mark remaining batch as error
          batchUploadFiles.forEach((uf) => {
            setFiles((prev) =>
              prev.map((f) =>
                f.id === uf.id
                  ? {
                      ...f,
                      status: 'error',
                      message: err.response?.data?.detail || 'Erro no upload em lote',
                    }
                  : f
              )
            );
          });
          totalErrors += batch.length;
        }

        setBulkProgress({ current: Math.min(i + batchSize, acceptedFiles.length), total: acceptedFiles.length });
      }

      setBulkUploading(false);

      if (totalUploaded > 0) {
        showSuccess(`${totalUploaded} arquivo(s) enviado(s) com sucesso`);
      }
      if (totalErrors > 0) {
        showError(`${totalErrors} arquivo(s) com erro`);
      }
    },
    [selectedCandidate, showSuccess, showError]
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length <= 3) {
        await uploadFilesSequentially(acceptedFiles);
      } else {
        await uploadFilesBulk(acceptedFiles);
      }
    },
    [uploadFilesSequentially, uploadFilesBulk]
  );

  // Handle folder selection
  const handleFolderSelect = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = event.target.files;
      if (!fileList || fileList.length === 0) return;

      // Filter supported files
      const supportedFiles: File[] = [];
      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];
        if (isSupportedFile(file)) {
          supportedFiles.push(file);
        }
      }

      if (supportedFiles.length === 0) {
        showError('Nenhum arquivo suportado encontrado na pasta selecionada');
        return;
      }

      const skipped = fileList.length - supportedFiles.length;
      if (skipped > 0) {
        showInfo(`${skipped} arquivo(s) ignorado(s) (formato nao suportado)`);
      }

      showInfo(`${supportedFiles.length} arquivo(s) encontrado(s) na pasta. Iniciando upload...`);

      await uploadFilesBulk(supportedFiles);

      // Reset input
      if (folderInputRef.current) {
        folderInputRef.current.value = '';
      }
    },
    [uploadFilesBulk, showError, showInfo]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt'],
      'application/rtf': ['.rtf'],
      'image/*': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'],
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
  const processingCount = files.filter((f) => f.status === 'processing' || f.status === 'uploading').length;

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Upload de Curriculos
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Envie curriculos individualmente ou selecione uma pasta inteira para upload em lote.
      </Typography>

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
                  helperText="Deixe em branco para criar um novo candidato automaticamente por arquivo"
                />
              )}
            />
          </Paper>

          {/* Upload Mode Tabs */}
          <Paper sx={{ mb: 3, border: '1px solid', borderColor: 'divider' }}>
            <Tabs
              value={tabValue}
              onChange={(_, v) => setTabValue(v)}
              sx={{ borderBottom: 1, borderColor: 'divider' }}
            >
              <Tab
                icon={<UploadFileIcon />}
                iconPosition="start"
                label="Arrastar Arquivos"
              />
              <Tab
                icon={<DriveFolderUpload />}
                iconPosition="start"
                label="Selecionar Pasta"
              />
            </Tabs>

            <Box sx={{ p: 3 }}>
              {tabValue === 0 && (
                /* Drop Zone */
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
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Selecione um ou multiplos arquivos (Ctrl+Click ou Shift+Click)
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Tamanho maximo: 20MB por arquivo
                      </Typography>
                      <Box display="flex" justifyContent="center" gap={1} flexWrap="wrap">
                        {['PDF', 'DOCX', 'DOC', 'TXT', 'RTF', 'JPG', 'PNG', 'TIFF'].map((fmt) => (
                          <Chip key={fmt} label={fmt} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </>
                  )}
                </Paper>
              )}

              {tabValue === 1 && (
                /* Folder Selection */
                <Box textAlign="center" py={4}>
                  <FolderOpen sx={{ fontSize: 64, color: 'primary.main', mb: 2, opacity: 0.8 }} />
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Selecionar Pasta para Upload em Lote
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Selecione uma pasta inteira do seu computador. Todos os arquivos suportados
                    serao enviados automaticamente (incluindo subpastas).
                  </Typography>

                  <input
                    ref={folderInputRef}
                    type="file"
                    /* @ts-ignore - webkitdirectory is non-standard but widely supported */
                    webkitdirectory=""
                    /* @ts-ignore */
                    directory=""
                    multiple
                    onChange={handleFolderSelect}
                    style={{ display: 'none' }}
                    id="folder-upload-input"
                  />

                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<DriveFolderUpload />}
                    onClick={() => folderInputRef.current?.click()}
                    disabled={bulkUploading}
                    sx={{ mb: 2, px: 4, py: 1.5 }}
                  >
                    {bulkUploading ? 'Enviando...' : 'Selecionar Pasta'}
                  </Button>

                  {bulkUploading && (
                    <Box sx={{ mt: 2 }}>
                      <LinearProgress
                        variant="determinate"
                        value={(bulkProgress.current / Math.max(bulkProgress.total, 1)) * 100}
                        sx={{ mb: 1, borderRadius: 1 }}
                      />
                      <Typography variant="body2" color="text.secondary">
                        {bulkProgress.current} de {bulkProgress.total} arquivo(s) enviado(s)
                      </Typography>
                    </Box>
                  )}

                  <Alert severity="info" sx={{ mt: 3, textAlign: 'left' }}>
                    <Typography variant="body2">
                      <strong>Formatos suportados:</strong> PDF, DOCX, DOC, TXT, RTF, ODT, JPG, JPEG, PNG, GIF, BMP, TIFF
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      <strong>Dica:</strong> Arquivos nao suportados serao ignorados automaticamente.
                      Para cada arquivo, um novo candidato sera criado e o curriculo sera processado com OCR.
                    </Typography>
                  </Alert>
                </Box>
              )}
            </Box>
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
                  { step: '1', text: 'Faca o upload do curriculo (arquivo ou pasta)' },
                  { step: '2', text: 'O sistema extrai o texto (OCR para PDFs escaneados e imagens)' },
                  { step: '3', text: 'Dados sao estruturados automaticamente (nome, email, experiencias)' },
                  { step: '4', text: 'Embeddings sao gerados para busca semantica' },
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
                  {processingCount > 0 && (
                    <Chip label={`${processingCount} processando`} size="small" color="info" />
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
        <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider', mt: 3 }}>
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
  );
};

export default UploadPage;
