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

const getFileIcon = (mimeType: string) => {
  if (mimeType.includes('pdf')) return <PictureAsPdf color="error" />;
  if (mimeType.includes('image')) return <Image color="primary" />;
  return <Article color="action" />;
};

const UploadPage: React.FC = () => {
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);

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
      'text/plain': ['.txt'],
      'image/*': ['.jpg', '.jpeg', '.png'],
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

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Upload de Curriculos
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Envie curriculos em PDF, DOCX, TXT ou imagens. O sistema extrai e analisa automaticamente.
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
                  {['PDF', 'DOCX', 'TXT', 'JPG', 'PNG'].map((fmt) => (
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
  );
};

export default UploadPage;
