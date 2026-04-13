import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
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
  Switch,
  FormControlLabel,
  Slider,
  Divider,
} from '@mui/material';
import {
  FolderOpen,
  Search as SearchIcon,
  CloudUpload,
  CheckCircle,
  Error as ErrorIcon,
  ContentCopy,
  SkipNext,
  Description,
  Info,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';

interface ScanFile {
  name: string;
  path: string;
  size_kb: number;
  extension: string;
}

interface ScanResult {
  folder_path: string;
  exists: boolean;
  readable: boolean;
  files_found: number;
  supported_files: number;
  files: ScanFile[];
  unsupported_files: string[];
  errors: string[];
}

interface ImportFileResult {
  filename: string;
  status: string;
  message: string;
  document_id?: number;
  candidate_id?: number;
}

interface ImportResult {
  total_files: number;
  imported: number;
  duplicates: number;
  errors: number;
  skipped: number;
  results: ImportFileResult[];
}

const statusColors: Record<string, 'success' | 'warning' | 'error' | 'default' | 'info'> = {
  imported: 'success',
  duplicate: 'info',
  error: 'error',
  skipped: 'default',
};

const statusIcons: Record<string, React.ReactElement> = {
  imported: <CheckCircle color="success" fontSize="small" />,
  duplicate: <ContentCopy color="info" fontSize="small" />,
  error: <ErrorIcon color="error" fontSize="small" />,
  skipped: <SkipNext color="disabled" fontSize="small" />,
};

const BatchImportPage: React.FC = () => {
  const { showSuccess, showError } = useNotification();
  const [folderPath, setFolderPath] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [maxFiles, setMaxFiles] = useState(100);
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  const handleScan = async () => {
    if (!folderPath.trim()) {
      showError('Informe o caminho da pasta');
      return;
    }
    setScanning(true);
    setImportResult(null);
    try {
      const data = await apiService.scanFolder(folderPath, recursive);
      setScanResult(data);
      if (data.supported_files > 0) {
        showSuccess(`${data.supported_files} curriculos encontrados!`);
      } else {
        showError('Nenhum arquivo suportado encontrado');
      }
    } catch (err: any) {
      showError('Erro ao escanear: ' + (err.response?.data?.detail || err.message));
    } finally {
      setScanning(false);
    }
  };

  const handleImport = async () => {
    if (!folderPath.trim()) return;
    setImporting(true);
    try {
      const data = await apiService.batchImport(folderPath, recursive, skipDuplicates, maxFiles);
      setImportResult(data);
      showSuccess(`Importacao concluida: ${data.imported} importados, ${data.duplicates} duplicados`);
    } catch (err: any) {
      showError('Erro na importacao: ' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(false);
    }
  };

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Importacao em Lote
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Importe curriculos de uma pasta local, pasta de rede ou drive compartilhado.
      </Typography>

      <Grid container spacing={3}>
        {/* Config panel */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Configuracao da Importacao
            </Typography>

            <TextField
              fullWidth
              label="Caminho da pasta"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder="/mnt/share/curriculos ou /home/user/Documents/CVs"
              helperText="Caminho absoluto da pasta no servidor. Pastas de rede devem estar montadas."
              sx={{ mb: 2 }}
            />

            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <FormControlLabel
                  control={<Switch checked={recursive} onChange={(e) => setRecursive(e.target.checked)} />}
                  label="Incluir subpastas"
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <FormControlLabel
                  control={<Switch checked={skipDuplicates} onChange={(e) => setSkipDuplicates(e.target.checked)} />}
                  label="Pular duplicados"
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="body2" gutterBottom>Max arquivos: {maxFiles}</Typography>
                <Slider
                  value={maxFiles}
                  onChange={(_, v) => setMaxFiles(v as number)}
                  min={10}
                  max={500}
                  step={10}
                  marks={[{ value: 10, label: '10' }, { value: 250, label: '250' }, { value: 500, label: '500' }]}
                />
              </Grid>
            </Grid>

            <Box display="flex" gap={2} mt={2}>
              <Button
                variant="outlined"
                startIcon={scanning ? <CircularProgress size={18} /> : <SearchIcon />}
                onClick={handleScan}
                disabled={scanning || !folderPath.trim()}
              >
                {scanning ? 'Escaneando...' : 'Escanear Pasta'}
              </Button>
              <Button
                variant="contained"
                startIcon={importing ? <CircularProgress size={18} color="inherit" /> : <CloudUpload />}
                onClick={handleImport}
                disabled={importing || !folderPath.trim()}
              >
                {importing ? 'Importando...' : 'Importar Curriculos'}
              </Button>
            </Box>
          </Paper>

          {/* Scan Results */}
          {scanResult && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Resultado do Escaneamento
              </Typography>

              {scanResult.errors.length > 0 && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {scanResult.errors.map((e, i) => (
                    <Typography key={i} variant="body2">{e}</Typography>
                  ))}
                </Alert>
              )}

              {scanResult.exists && scanResult.readable && (
                <>
                  <Box display="flex" gap={1} mb={2} flexWrap="wrap">
                    <Chip label={`${scanResult.files_found} arquivos total`} />
                    <Chip label={`${scanResult.supported_files} suportados`} color="success" />
                    {scanResult.unsupported_files.length > 0 && (
                      <Chip label={`${scanResult.unsupported_files.length} nao suportados`} color="warning" />
                    )}
                  </Box>

                  <List dense sx={{ maxHeight: 400, overflow: 'auto' }}>
                    {scanResult.files.map((file, idx) => (
                      <ListItem key={idx}>
                        <ListItemIcon><Description fontSize="small" /></ListItemIcon>
                        <ListItemText
                          primary={file.name}
                          secondary={`${file.size_kb} KB | ${file.extension}`}
                          primaryTypographyProps={{ variant: 'body2' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </>
              )}
            </Paper>
          )}

          {/* Import Results */}
          {importResult && (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Resultado da Importacao
              </Typography>

              <Box display="flex" gap={1} mb={2} flexWrap="wrap">
                <Chip label={`${importResult.total_files} total`} />
                <Chip label={`${importResult.imported} importados`} color="success" />
                <Chip label={`${importResult.duplicates} duplicados`} color="info" />
                {importResult.errors > 0 && <Chip label={`${importResult.errors} erros`} color="error" />}
                {importResult.skipped > 0 && <Chip label={`${importResult.skipped} pulados`} />}
              </Box>

              <List dense sx={{ maxHeight: 500, overflow: 'auto' }}>
                {importResult.results.map((r, idx) => (
                  <ListItem key={idx}>
                    <ListItemIcon>{statusIcons[r.status] || <Info fontSize="small" />}</ListItemIcon>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="body2" fontWeight={500}>{r.filename}</Typography>
                          <Chip label={r.status} size="small" color={statusColors[r.status] || 'default'} variant="outlined" />
                        </Box>
                      }
                      secondary={r.message}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          )}
        </Grid>

        {/* Info sidebar */}
        <Grid item xs={12} md={4}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Como Funciona
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {[
                  { step: '1', text: 'Informe o caminho da pasta com curriculos' },
                  { step: '2', text: 'Escaneie para ver os arquivos encontrados' },
                  { step: '3', text: 'Clique em Importar para processar todos' },
                  { step: '4', text: 'Cada arquivo e copiado, parseado e vetorizado' },
                ].map((item) => (
                  <Box key={item.step} display="flex" gap={1.5} alignItems="center">
                    <Chip label={item.step} size="small" color="primary" sx={{ fontWeight: 700, minWidth: 28 }} />
                    <Typography variant="body2">{item.text}</Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Formatos Suportados
              </Typography>
              <Box display="flex" gap={0.5} flexWrap="wrap">
                {['PDF', 'DOCX', 'DOC', 'TXT', 'RTF', 'JPG', 'PNG', 'TIFF', 'BMP'].map((fmt) => (
                  <Chip key={fmt} label={fmt} size="small" variant="outlined" />
                ))}
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Exemplos de Caminho
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                <strong>Pasta local:</strong>
              </Typography>
              <Typography variant="caption" fontFamily="monospace" display="block" sx={{ mb: 1 }}>
                /home/usuario/curriculos
              </Typography>

              <Typography variant="body2" color="text.secondary" gutterBottom>
                <strong>Rede (SMB/CIFS montada):</strong>
              </Typography>
              <Typography variant="caption" fontFamily="monospace" display="block" sx={{ mb: 1 }}>
                /mnt/share/rh/curriculos
              </Typography>

              <Typography variant="body2" color="text.secondary" gutterBottom>
                <strong>Google Drive (rclone):</strong>
              </Typography>
              <Typography variant="caption" fontFamily="monospace" display="block" sx={{ mb: 1 }}>
                /mnt/gdrive/Curriculos
              </Typography>

              <Divider sx={{ my: 1.5 }} />
              <Alert severity="info" variant="outlined" sx={{ '& .MuiAlert-message': { fontSize: '0.75rem' } }}>
                Pastas de rede devem estar montadas no servidor. Use mount, fstab, ou rclone para montar antes de importar.
              </Alert>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default BatchImportPage;
