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
  Alert,
  Autocomplete,
  TextField,
} from '@mui/material';
import { CloudUpload, Description, CheckCircle, Error } from '@mui/icons-material';
import { apiService } from '../services/api';
import { websocketService } from '../services/websocket';
import { Candidate, WebSocketMessage } from '../types';

interface UploadFile {
  file: File;
  documentId?: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  message: string;
}

const UploadPage: React.FC = () => {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    // Fetch candidates for selection
    const fetchCandidates = async () => {
      try {
        const data = await apiService.getCandidates();
        setCandidates(data);
      } catch (error) {
        console.error('Error fetching candidates:', error);
      }
    };

    fetchCandidates();

    // Setup WebSocket listener for document progress
    const handleProgress = (message: WebSocketMessage) => {
      if (message.type === 'document_progress' && message.document_id) {
        setFiles((prevFiles) =>
          prevFiles.map((f) =>
            f.documentId === message.document_id
              ? {
                  ...f,
                  status: message.status as any,
                  progress: message.progress || 0,
                  message: message.message || '',
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
      setError('');

      // Add files to state
      const newFiles: UploadFile[] = acceptedFiles.map((file) => ({
        file,
        status: 'pending',
        progress: 0,
        message: 'Aguardando upload',
      }));

      setFiles((prev) => [...prev, ...newFiles]);

      // Upload each file
      for (const uploadFile of newFiles) {
        try {
          // Update status to uploading
          setFiles((prev) =>
            prev.map((f) =>
              f.file === uploadFile.file
                ? { ...f, status: 'uploading', message: 'Fazendo upload...' }
                : f
            )
          );

          // Upload document
          const document = await apiService.uploadDocument(
            uploadFile.file,
            selectedCandidate?.id
          );

          // Update with document ID and subscribe to progress
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

          // Subscribe to WebSocket updates for this document
          websocketService.subscribeDocument(document.id);
        } catch (err: any) {
          console.error('Upload error:', err);
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
        }
      }
    },
    [selectedCandidate]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'image/*': ['.jpg', '.jpeg', '.png'],
    },
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'error':
        return <Error color="error" />;
      default:
        return <Description />;
    }
  };

  const clearCompleted = () => {
    setFiles((prev) => prev.filter((f) => f.status !== 'completed'));
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Upload de Currículos
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Autocomplete
          options={candidates}
          getOptionLabel={(option) => option.full_name}
          value={selectedCandidate}
          onChange={(_, newValue) => setSelectedCandidate(newValue)}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Candidato (opcional)"
              helperText="Deixe em branco para criar um novo candidato automaticamente"
            />
          )}
          sx={{ mb: 3 }}
        />

        <Paper
          {...getRootProps()}
          sx={{
            p: 5,
            textAlign: 'center',
            border: '2px dashed',
            borderColor: isDragActive ? 'primary.main' : 'grey.300',
            backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              borderColor: 'primary.main',
              backgroundColor: 'action.hover',
            },
          }}
        >
          <input {...getInputProps()} />
          <CloudUpload sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          {isDragActive ? (
            <Typography variant="h6">Solte os arquivos aqui...</Typography>
          ) : (
            <>
              <Typography variant="h6" gutterBottom>
                Arraste arquivos aqui ou clique para selecionar
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Formatos suportados: PDF, DOCX, TXT, JPG, PNG
              </Typography>
            </>
          )}
        </Paper>
      </Paper>

      {files.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Arquivos</Typography>
            <Button onClick={clearCompleted} size="small">
              Limpar Concluídos
            </Button>
          </Box>

          <List>
            {files.map((uploadFile, index) => (
              <ListItem key={index}>
                <ListItemIcon>{getStatusIcon(uploadFile.status)}</ListItemIcon>
                <ListItemText
                  primary={uploadFile.file.name}
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        {uploadFile.message}
                      </Typography>
                      {(uploadFile.status === 'uploading' || uploadFile.status === 'processing') && (
                        <LinearProgress
                          variant="determinate"
                          value={uploadFile.progress}
                          sx={{ mt: 1 }}
                        />
                      )}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </Paper>
      )}
    </Box>
  );
};

export default UploadPage;
