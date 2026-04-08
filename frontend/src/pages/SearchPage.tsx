import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  ToggleButtonGroup,
  ToggleButton,
  Card,
  CardContent,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  InputAdornment,
  Slider,
  Collapse,
  IconButton,
  Tooltip,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Search as SearchIcon,
  Tune,
  Person,
  ExpandMore,
  ExpandLess,
  OpenInNew,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { SearchResult } from '../types';
import { useNotification } from '../contexts/NotificationContext';

const SearchPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { showError } = useNotification();
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic'>('hybrid');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [topK, setTopK] = useState(10);
  const [showFilters, setShowFilters] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) {
      showError('Digite uma consulta de busca');
      return;
    }

    setLoading(true);
    setSearched(true);

    try {
      let searchResults;
      if (searchType === 'semantic') {
        searchResults = await apiService.semanticSearch(query, topK);
      } else {
        searchResults = await apiService.hybridSearch(query, {}, topK);
      }
      setResults(searchResults);
    } catch (err: any) {
      showError(err.response?.data?.detail || 'Erro ao realizar busca');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const getScoreColor = (score: number): 'success' | 'warning' | 'error' | 'primary' => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'primary';
    if (score >= 0.4) return 'warning';
    return 'error';
  };

  return (
    <Box className="fade-in">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Busca Inteligente
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Encontre candidatos usando busca semantica com IA ou busca hibrida
      </Typography>

      {/* Search Box */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <TextField
          fullWidth
          placeholder="Ex: operador de producao com experiencia em CNC e NR-12"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          sx={{ mb: 2 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="action" />
              </InputAdornment>
            ),
          }}
          size="medium"
        />

        <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
          <Box display="flex" alignItems="center" gap={2}>
            <ToggleButtonGroup
              value={searchType}
              exclusive
              onChange={(_, v) => v && setSearchType(v)}
              size="small"
            >
              <ToggleButton value="hybrid">Hibrida</ToggleButton>
              <ToggleButton value="semantic">Semantica</ToggleButton>
            </ToggleButtonGroup>
            <Tooltip title="Filtros avancados">
              <IconButton size="small" onClick={() => setShowFilters(!showFilters)}>
                <Tune />
              </IconButton>
            </Tooltip>
          </Box>

          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <SearchIcon />}
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            sx={{ px: 4 }}
          >
            {loading ? 'Buscando...' : 'Buscar'}
          </Button>
        </Box>

        <Collapse in={showFilters}>
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            <Typography variant="body2" fontWeight={500} gutterBottom>
              Numero maximo de resultados: {topK}
            </Typography>
            <Slider
              value={topK}
              onChange={(_, v) => setTopK(v as number)}
              min={5}
              max={50}
              step={5}
              marks
              sx={{ maxWidth: 300 }}
            />
          </Box>
        </Collapse>
      </Paper>

      {/* Results */}
      {loading ? (
        <Box display="flex" justifyContent="center" p={5}>
          <Box textAlign="center">
            <CircularProgress size={40} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Analisando curriculos na base de dados...
            </Typography>
          </Box>
        </Box>
      ) : results.length > 0 ? (
        <Box>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6" fontWeight={600}>
              {results.length} candidato(s) encontrado(s)
            </Typography>
            <Chip
              label={searchType === 'hybrid' ? 'Busca Hibrida' : 'Busca Semantica'}
              size="small"
              color="primary"
              variant="outlined"
            />
          </Box>

          <Grid container spacing={2}>
            {results.map((result, index) => (
              <Grid item xs={12} key={index}>
                <Card
                  sx={{
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      transform: 'translateY(-1px)',
                      boxShadow: theme.shadows[3],
                    },
                  }}
                  onClick={() => navigate(`/candidates/${result.candidate_id}`)}
                >
                  <CardContent sx={{ p: 3 }}>
                    <Box display="flex" justifyContent="space-between" alignItems="start" mb={1.5}>
                      <Box display="flex" alignItems="center" gap={1.5}>
                        <Box
                          sx={{
                            p: 1,
                            borderRadius: 2,
                            bgcolor: alpha(theme.palette.primary.main, 0.1),
                          }}
                        >
                          <Person color="primary" />
                        </Box>
                        <Box>
                          <Typography variant="subtitle1" fontWeight={600}>
                            {result.candidate_name}
                          </Typography>
                          {(result.email || result.city) && (
                            <Typography variant="caption" color="text.secondary">
                              {result.email} {result.city ? `- ${result.city}/${result.state}` : ''}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                      <Chip
                        label={`${(result.score * 100).toFixed(1)}%`}
                        color={getScoreColor(result.score)}
                        size="small"
                        sx={{ fontWeight: 600 }}
                      />
                    </Box>

                    {result.matched_chunks && result.matched_chunks.length > 0 && (
                      <Box>
                        <Typography variant="caption" color="text.secondary" fontWeight={500}>
                          Trechos relevantes:
                        </Typography>
                        {result.matched_chunks.slice(0, 2).map((chunk, i) => (
                          <Paper
                            key={i}
                            sx={{
                              p: 1.5,
                              mt: 1,
                              bgcolor: alpha(theme.palette.primary.main, 0.04),
                              border: '1px solid',
                              borderColor: 'divider',
                            }}
                          >
                            <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                              <Chip label={chunk.section} size="small" variant="outlined" />
                              <Typography variant="caption" color="text.secondary">
                                {(chunk.similarity * 100).toFixed(0)}% relevante
                              </Typography>
                            </Box>
                            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
                              {chunk.content.substring(0, 250)}
                              {chunk.content.length > 250 ? '...' : ''}
                            </Typography>
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
      ) : searched && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
          <SearchIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Nenhum resultado encontrado
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Tente usar termos diferentes ou a busca semantica para resultados mais amplos
          </Typography>
        </Paper>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
          <SearchIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Faca uma busca
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 500, mx: 'auto' }}>
            Use linguagem natural para encontrar candidatos. A busca hibrida combina similaridade
            semantica com busca textual para os melhores resultados.
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default SearchPage;
