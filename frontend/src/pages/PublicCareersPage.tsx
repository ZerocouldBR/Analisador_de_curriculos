import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Container,
  CircularProgress,
  Grid,
  Avatar,
  Link as MuiLink,
  ThemeProvider,
  createTheme,
} from '@mui/material';
import { LocationOn, Work, Timer } from '@mui/icons-material';
import { apiService } from '../services/api';
import { PublicJobsPageResponse } from '../types';

/**
 * Pagina publica de vagas de uma empresa.
 * Acessivel sem autenticacao via /careers/:companySlug
 */
const PublicCareersPage: React.FC = () => {
  const { companySlug } = useParams<{ companySlug: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<PublicJobsPageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companySlug) return;
    apiService
      .getPublicCareersPage(companySlug)
      .then((resp) => setData(resp))
      .catch(() => setError('Empresa nao encontrada'))
      .finally(() => setLoading(false));
  }, [companySlug]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Container maxWidth="md" sx={{ py: 8 }}>
        <Typography variant="h4">Pagina nao encontrada</Typography>
        <Typography color="text.secondary">{error}</Typography>
      </Container>
    );
  }

  const brand = data.company;
  const brandColor = brand.brand_color || '#1976d2';
  const pageTheme = createTheme({
    palette: { primary: { main: brandColor } },
  });

  return (
    <ThemeProvider theme={pageTheme}>
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
        <Box
          sx={{
            bgcolor: brandColor,
            color: '#fff',
            py: 6,
            borderBottom: `4px solid ${brandColor}`,
          }}
        >
          <Container maxWidth="lg">
            <Box display="flex" alignItems="center" gap={3}>
              {brand.logo_url && (
                <Avatar
                  src={brand.logo_url.startsWith('http') ? brand.logo_url : undefined}
                  sx={{ width: 80, height: 80, bgcolor: 'rgba(255,255,255,0.2)' }}
                />
              )}
              <Box>
                <Typography variant="h3" fontWeight={700}>
                  {brand.name}
                </Typography>
                <Typography variant="subtitle1" sx={{ opacity: 0.9 }}>
                  Vagas abertas
                </Typography>
                {brand.website && (
                  <MuiLink
                    href={brand.website}
                    target="_blank"
                    rel="noopener"
                    sx={{ color: '#fff', opacity: 0.9, mt: 1, display: 'inline-block' }}
                  >
                    {brand.website}
                  </MuiLink>
                )}
              </Box>
            </Box>
            {brand.about && (
              <Typography variant="body1" mt={3} sx={{ maxWidth: 800 }}>
                {brand.about}
              </Typography>
            )}
          </Container>
        </Box>

        <Container maxWidth="lg" sx={{ py: 6 }}>
          {data.jobs.length === 0 ? (
            <Box textAlign="center" py={8}>
              <Work sx={{ fontSize: 64, color: 'text.disabled' }} />
              <Typography variant="h5" mt={2}>
                Nenhuma vaga aberta no momento
              </Typography>
              <Typography color="text.secondary">
                Volte em breve para ver novas oportunidades
              </Typography>
            </Box>
          ) : (
            <Grid container spacing={2}>
              {data.jobs.map((job) => (
                <Grid item xs={12} md={6} key={job.slug}>
                  <Card sx={{ height: '100%' }}>
                    <CardActionArea
                      onClick={() => navigate(`/careers/${companySlug}/${job.slug}`)}
                      sx={{ height: '100%' }}
                    >
                      <CardContent>
                        <Typography variant="h6" fontWeight={600}>
                          {job.title}
                        </Typography>
                        <Box display="flex" flexWrap="wrap" gap={1} mt={1}>
                          {job.location && (
                            <Chip
                              size="small"
                              icon={<LocationOn fontSize="small" />}
                              label={job.location}
                            />
                          )}
                          {job.work_mode && (
                            <Chip size="small" label={job.work_mode} variant="outlined" />
                          )}
                          {job.employment_type && (
                            <Chip size="small" label={job.employment_type} variant="outlined" />
                          )}
                          {job.seniority_level && (
                            <Chip size="small" label={job.seniority_level} variant="outlined" />
                          )}
                        </Box>
                        {job.salary_display && (
                          <Typography variant="body2" color="primary" mt={2} fontWeight={600}>
                            {job.salary_display}
                          </Typography>
                        )}
                        {job.published_at && (
                          <Box display="flex" alignItems="center" gap={0.5} mt={1.5}>
                            <Timer fontSize="inherit" color="action" />
                            <Typography variant="caption" color="text.secondary">
                              Publicada em {new Date(job.published_at).toLocaleDateString('pt-BR')}
                            </Typography>
                          </Box>
                        )}
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Container>
      </Box>
    </ThemeProvider>
  );
};

export default PublicCareersPage;
