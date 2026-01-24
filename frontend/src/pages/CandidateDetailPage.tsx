import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Button,
  CircularProgress,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import { ArrowBack, Email, Phone, LocationOn } from '@mui/icons-material';
import { apiService } from '../services/api';
import { Candidate, Document } from '../types';

const CandidateDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;

      try {
        const [candidateData, documentsData] = await Promise.all([
          apiService.getCandidate(parseInt(id)),
          apiService.getCandidateDocuments(parseInt(id)),
        ]);

        setCandidate(candidateData);
        setDocuments(documentsData);
      } catch (error) {
        console.error('Error fetching candidate details:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!candidate) {
    return (
      <Box>
        <Typography variant="h5">Candidato não encontrado</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate('/candidates')}
        sx={{ mb: 2 }}
      >
        Voltar
      </Button>

      <Typography variant="h4" gutterBottom>
        {candidate.full_name}
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Informações Pessoais
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Email color="action" />
                  <Typography>{candidate.email || 'Não informado'}</Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Phone color="action" />
                  <Typography>{candidate.phone || 'Não informado'}</Typography>
                </Box>
              </Grid>
              <Grid item xs={12}>
                <Box display="flex" alignItems="center" gap={1}>
                  <LocationOn color="action" />
                  <Typography>
                    {candidate.city && candidate.state
                      ? `${candidate.city}, ${candidate.state}`
                      : 'Não informado'}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>

          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Documentos
            </Typography>
            <List>
              {documents.length === 0 ? (
                <ListItem>
                  <ListItemText primary="Nenhum documento enviado" />
                </ListItem>
              ) : (
                documents.map((doc) => (
                  <ListItem key={doc.id}>
                    <ListItemText
                      primary={doc.original_filename}
                      secondary={`Enviado em: ${new Date(doc.uploaded_at).toLocaleString()}`}
                    />
                    <Chip label={doc.mime_type} size="small" />
                  </ListItem>
                ))
              )}
            </List>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Estatísticas
              </Typography>
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Total de Documentos
                </Typography>
                <Typography variant="h4">{documents.length}</Typography>
              </Box>
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Cadastrado em
                </Typography>
                <Typography variant="body1">
                  {new Date(candidate.created_at).toLocaleDateString()}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CandidateDetailPage;
