import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  RadioGroup,
  FormControlLabel,
  Radio,
  Card,
  CardContent,
  Grid,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { apiService } from '../services/api';
import { SearchResult } from '../types';

const SearchPage: React.FC = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'semantic' | 'hybrid'>('hybrid');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async () => {
    if (!query.trim()) {
      setError('Por favor, digite uma consulta de busca');
      return;
    }

    setError('');
    setLoading(true);

    try {
      let searchResults;
      if (searchType === 'semantic') {
        searchResults = await apiService.semanticSearch(query, 10);
      } else {
        searchResults = await apiService.hybridSearch(query, {}, 10);
      }

      setResults(searchResults);
    } catch (err: any) {
      console.error('Search error:', err);
      setError(err.response?.data?.detail || 'Erro ao realizar busca');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Busca de Candidatos
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <TextField
          fullWidth
          label="Digite sua busca"
          placeholder="Ex: desenvolvedor Python com 5 anos de experiência"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          sx={{ mb: 2 }}
        />

        <Box display="flex" justifyContent="space-between" alignItems="center">
          <RadioGroup
            row
            value={searchType}
            onChange={(e) => setSearchType(e.target.value as 'semantic' | 'hybrid')}
          >
            <FormControlLabel
              value="hybrid"
              control={<Radio />}
              label="Busca Híbrida (Recomendado)"
            />
            <FormControlLabel
              value="semantic"
              control={<Radio />}
              label="Busca Semântica"
            />
          </RadioGroup>

          <Button
            variant="contained"
            startIcon={<SearchIcon />}
            onClick={handleSearch}
            disabled={loading}
          >
            {loading ? 'Buscando...' : 'Buscar'}
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Paper>

      {loading ? (
        <Box display="flex" justifyContent="center" p={5}>
          <CircularProgress />
        </Box>
      ) : results.length > 0 ? (
        <Box>
          <Typography variant="h6" gutterBottom>
            {results.length} candidato(s) encontrado(s)
          </Typography>

          <Grid container spacing={2}>
            {results.map((result, index) => (
              <Grid item xs={12} key={index}>
                <Card
                  sx={{
                    cursor: 'pointer',
                    '&:hover': {
                      boxShadow: 3,
                    },
                  }}
                  onClick={() => navigate(`/candidates/${result.candidate_id}`)}
                >
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
                      <Typography variant="h6">{result.candidate_name}</Typography>
                      <Chip
                        label={`Score: ${(result.score * 100).toFixed(1)}%`}
                        color="primary"
                        size="small"
                      />
                    </Box>

                    {result.matched_chunks && result.matched_chunks.length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                          Trechos relevantes:
                        </Typography>
                        {result.matched_chunks.slice(0, 2).map((chunk, i) => (
                          <Paper
                            key={i}
                            sx={{
                              p: 1.5,
                              mb: 1,
                              backgroundColor: 'grey.50',
                            }}
                          >
                            <Typography variant="caption" color="text.secondary">
                              {chunk.section}
                            </Typography>
                            <Typography variant="body2">
                              {chunk.content.substring(0, 200)}
                              {chunk.content.length > 200 ? '...' : ''}
                            </Typography>
                            <Chip
                              label={`${(chunk.similarity * 100).toFixed(0)}% relevante`}
                              size="small"
                              sx={{ mt: 1 }}
                            />
                          </Paper>
                        ))}
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      ) : query && !loading ? (
        <Alert severity="info">Nenhum candidato encontrado para esta busca.</Alert>
      ) : null}
    </Box>
  );
};

export default SearchPage;
