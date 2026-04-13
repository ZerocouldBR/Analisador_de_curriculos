import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  Divider,
  InputAdornment,
  CircularProgress,
  Tab,
  Tabs,
  useTheme,
  alpha,
  Autocomplete,
  Alert,
} from '@mui/material';
import {
  LinkedIn,
  Search,
  Person,
  Link as LinkIcon,
  Work,
  LocationOn,
  OpenInNew,
  MenuBook,
  Info,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { useNotification } from '../contexts/NotificationContext';

interface EnrichmentData {
  headline?: string;
  summary?: string;
  skills?: string[];
  certifications?: string[];
  languages?: string[];
}

const LinkedInPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { showSuccess, showError } = useNotification();
  const [tab, setTab] = useState(0);

  // Enrichment
  const [profileUrl, setProfileUrl] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState<any>(null);

  // Manual enrichment
  const [candidateId, setCandidateId] = useState('');
  const [enrichData, setEnrichData] = useState<EnrichmentData>({
    headline: '',
    summary: '',
    skills: [],
    certifications: [],
    languages: [],
  });
  const [enriching, setEnriching] = useState(false);

  // Skills input
  const [skillInput, setSkillInput] = useState('');

  const handleExtract = async () => {
    if (!profileUrl.trim()) {
      showError('Informe a URL do perfil do LinkedIn');
      return;
    }
    setExtracting(true);
    setExtractedData(null);
    try {
      const data = await apiService.linkedInExtract(profileUrl);
      setExtractedData(data);
      showSuccess('Dados extraidos com sucesso');
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro ao extrair dados do LinkedIn');
    } finally {
      setExtracting(false);
    }
  };

  const handleManualEnrich = async () => {
    if (!candidateId) {
      showError('Informe o ID do candidato');
      return;
    }
    setEnriching(true);
    try {
      await apiService.linkedInManualEnrich(parseInt(candidateId), enrichData);
      showSuccess('Enriquecimento realizado com sucesso');
      setEnrichData({ headline: '', summary: '', skills: [], certifications: [], languages: [] });
      setCandidateId('');
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Erro no enriquecimento');
    } finally {
      setEnriching(false);
    }
  };

  const addSkill = () => {
    if (skillInput.trim() && !enrichData.skills?.includes(skillInput.trim())) {
      setEnrichData({
        ...enrichData,
        skills: [...(enrichData.skills || []), skillInput.trim()],
      });
      setSkillInput('');
    }
  };

  const removeSkill = (skill: string) => {
    setEnrichData({
      ...enrichData,
      skills: enrichData.skills?.filter((s) => s !== skill) || [],
    });
  };

  return (
    <Box className="fade-in">
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Box
          sx={{
            p: 1.5,
            borderRadius: 2,
            bgcolor: alpha('#0077b5', 0.1),
          }}
        >
          <LinkedIn sx={{ fontSize: 32, color: '#0077b5' }} />
        </Box>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Integracao LinkedIn
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Extraia e enriqueca perfis de candidatos com dados do LinkedIn
          </Typography>
        </Box>
      </Box>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Extrair Perfil" icon={<LinkIcon />} iconPosition="start" />
        <Tab label="Enriquecimento Manual" icon={<Person />} iconPosition="start" />
        <Tab label="Guia de Integracao" icon={<MenuBook />} iconPosition="start" />
      </Tabs>

      {/* Extract Profile Tab */}
      {tab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Extrair Dados de Perfil
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Insira a URL do perfil publico do LinkedIn para extrair informacoes do candidato.
              </Typography>

              <TextField
                fullWidth
                label="URL do Perfil LinkedIn"
                placeholder="https://linkedin.com/in/nome-do-candidato"
                value={profileUrl}
                onChange={(e) => setProfileUrl(e.target.value)}
                sx={{ mb: 2 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LinkedIn sx={{ color: '#0077b5' }} />
                    </InputAdornment>
                  ),
                }}
              />

              <Button
                variant="contained"
                startIcon={extracting ? <CircularProgress size={18} color="inherit" /> : <Search />}
                onClick={handleExtract}
                disabled={extracting || !profileUrl.trim()}
              >
                {extracting ? 'Extraindo...' : 'Extrair Dados'}
              </Button>
            </Paper>

            {/* Extracted Results */}
            {extractedData && (
              <Paper sx={{ p: 3, mt: 3, border: '1px solid', borderColor: 'divider' }}>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Dados Extraidos
                </Typography>
                <Box
                  sx={{
                    p: 2,
                    bgcolor: alpha(theme.palette.success.main, 0.05),
                    borderRadius: 2,
                    border: '1px solid',
                    borderColor: alpha(theme.palette.success.main, 0.2),
                  }}
                >
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                    {JSON.stringify(extractedData, null, 2)}
                  </pre>
                </Box>
              </Paper>
            )}
          </Grid>

          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Como funciona
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                  {[
                    { step: '1', text: 'Cole a URL do perfil publico' },
                    { step: '2', text: 'O sistema extrai os dados disponiveis' },
                    { step: '3', text: 'Os dados sao vinculados ao candidato' },
                    { step: '4', text: 'Perfil enriquecido com informacoes adicionais' },
                  ].map((item) => (
                    <Box key={item.step} display="flex" gap={1.5} alignItems="center">
                      <Chip label={item.step} size="small" color="primary" sx={{ fontWeight: 700, minWidth: 28 }} />
                      <Typography variant="body2">{item.text}</Typography>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Integration Guide Tab */}
      {tab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="h5" fontWeight={700} gutterBottom>
                Guia Completo: Buscar Curriculos pelo LinkedIn
              </Typography>

              <Alert severity="info" sx={{ mb: 3 }}>
                O LinkedIn restringe scraping automatico. Para buscar perfis de pessoas-chave,
                use uma das abordagens oficiais ou autorizadas abaixo.
              </Alert>

              {/* Opcao 1: Proxycurl */}
              <Typography variant="h6" fontWeight={600} gutterBottom sx={{ mt: 3 }}>
                1. Proxycurl API (Recomendado)
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Servico pago que fornece API oficial para dados do LinkedIn. Mais confiavel e dentro dos termos de uso.
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
{`Passo a passo:
1. Crie conta em https://nubela.co/proxycurl
2. Obtenha sua API key
3. Configure no .env do backend:
   PROXYCURL_API_KEY=sua_chave_aqui

4. Exemplo de uso na API:
   curl -H "Authorization: Bearer SUA_KEY" \\
     "https://nubela.co/proxycurl/api/v2/linkedin?url=https://linkedin.com/in/pessoa"

5. Retorna JSON com: nome, cargo, empresa, skills, educacao, experiencias`}
                </Typography>
              </Paper>

              {/* Opcao 2: RapidAPI */}
              <Typography variant="h6" fontWeight={600} gutterBottom sx={{ mt: 3 }}>
                2. RapidAPI - LinkedIn Endpoints
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Marketplace com varios provedores de dados LinkedIn. Planos gratuitos limitados disponiveis.
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
{`Passo a passo:
1. Acesse https://rapidapi.com e crie conta
2. Busque por "LinkedIn Profile" ou "LinkedIn Data"
3. Provedores recomendados:
   - "Fresh LinkedIn Profile Data" (melhor custo-beneficio)
   - "LinkedIn Profile and Company Data"
4. Assine um plano e copie sua X-RapidAPI-Key
5. Configure no .env:
   RAPIDAPI_KEY=sua_chave_aqui
   RAPIDAPI_HOST=fresh-linkedin-profile-data.p.rapidapi.com`}
                </Typography>
              </Paper>

              {/* Opcao 3: PhantomBuster */}
              <Typography variant="h6" fontWeight={600} gutterBottom sx={{ mt: 3 }}>
                3. PhantomBuster (Automacao Visual)
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Ferramenta de automacao que simula navegacao no LinkedIn. Ideal para buscar perfis em massa.
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
{`Passo a passo para buscar pessoas-chave:
1. Crie conta em https://phantombuster.com
2. Use o Phantom "LinkedIn Profile Scraper"
3. Configure:
   - Cookie de sessao do LinkedIn (li_at)
   - Lista de URLs de perfis OU termos de busca
4. O Phantom coleta: nome, cargo, empresa, localizacao, skills
5. Exporte CSV e importe no sistema via "Enriquecimento Manual"

Para buscar por cargo/empresa especifica:
1. Use o Phantom "LinkedIn Search Export"
2. Configure a busca: "Gerente de Producao" em "Sao Paulo"
3. Exporte resultados com URLs dos perfis
4. Use os URLs no Phantom "LinkedIn Profile Scraper"`}
                </Typography>
              </Paper>

              {/* Opcao 4: LinkedIn API Oficial */}
              <Typography variant="h6" fontWeight={600} gutterBottom sx={{ mt: 3 }}>
                4. LinkedIn API Oficial (Para Empresas)
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Requer parceria com o LinkedIn. Acesso mais completo, mas processo de aprovacao demorado.
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
{`Passo a passo:
1. Acesse https://developer.linkedin.com
2. Crie um App em "My Apps"
3. Solicite os produtos:
   - "Sign In with LinkedIn using OpenID Connect"
   - "Share on LinkedIn" (para postar vagas)
   - Para dados de perfil: solicite "Marketing Developer Platform"
4. Configure OAuth 2.0:
   LINKEDIN_CLIENT_ID=seu_client_id
   LINKEDIN_CLIENT_SECRET=seu_client_secret
   LINKEDIN_REDIRECT_URI=https://seusite.com/api/v1/linkedin/callback
5. O usuario autoriza via OAuth e voce acessa o perfil dele

IMPORTANTE: A API oficial so acessa dados de usuarios que
autorizarem via OAuth. NAO permite buscar perfis arbitrarios.`}
                </Typography>
              </Paper>

              {/* Opcao 5: Manual com CSV */}
              <Typography variant="h6" fontWeight={600} gutterBottom sx={{ mt: 3 }}>
                5. Busca Manual + Importacao (Sem Custo)
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Para equipes pequenas: busque manualmente e use o enriquecimento manual do sistema.
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
{`Passo a passo para buscar pessoas-chave:
1. Acesse linkedin.com e faca login
2. Use a busca avancada:
   - Filtro "Pessoas"
   - Cargo: "Gerente de Producao" ou "Operador CNC"
   - Localizacao: "Sao Leopoldo, RS"
   - Empresa atual: nome da empresa alvo
3. Para cada perfil relevante:
   a. Copie a URL do perfil
   b. Copie os dados: nome, cargo, skills, experiencia
4. No sistema, va em "Enriquecimento Manual"
5. Insira o ID do candidato e os dados copiados
6. O sistema indexa para busca semantica

Dica: Use LinkedIn Sales Navigator para busca avancada
(filtros por senioridade, tamanho da empresa, etc.)`}
                </Typography>
              </Paper>
            </Paper>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Comparativo de Opcoes
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  {[
                    { name: 'Proxycurl', cost: '$$', reliability: 'Alta', setup: 'Facil' },
                    { name: 'RapidAPI', cost: '$-$$', reliability: 'Media', setup: 'Facil' },
                    { name: 'PhantomBuster', cost: '$$', reliability: 'Media', setup: 'Media' },
                    { name: 'API Oficial', cost: 'Gratis', reliability: 'Alta', setup: 'Dificil' },
                    { name: 'Manual', cost: 'Gratis', reliability: 'Alta', setup: 'Sem setup' },
                  ].map((opt) => (
                    <Box key={opt.name} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                      <Typography variant="body2" fontWeight={600}>{opt.name}</Typography>
                      <Box display="flex" gap={0.5} mt={0.5}>
                        <Chip label={`Custo: ${opt.cost}`} size="small" variant="outlined" />
                        <Chip label={opt.reliability} size="small" color="success" variant="outlined" />
                      </Box>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Variaveis de Ambiente
                </Typography>
                <Paper sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="caption" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
{`# .env do backend
LINKEDIN_API_ENABLED=true
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=

# Opcional (servicos terceiros)
PROXYCURL_API_KEY=
RAPIDAPI_KEY=`}
                  </Typography>
                </Paper>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Manual Enrichment Tab */}
      {tab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Enriquecimento Manual de Candidato
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Adicione informacoes do LinkedIn manualmente a um candidato existente.
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                <TextField
                  label="ID do Candidato"
                  type="number"
                  value={candidateId}
                  onChange={(e) => setCandidateId(e.target.value)}
                  fullWidth
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Person color="action" />
                      </InputAdornment>
                    ),
                  }}
                />

                <TextField
                  label="Headline / Titulo Profissional"
                  value={enrichData.headline}
                  onChange={(e) => setEnrichData({ ...enrichData, headline: e.target.value })}
                  fullWidth
                  placeholder="Ex: Engenheiro de Producao | Especialista em Lean"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Work color="action" />
                      </InputAdornment>
                    ),
                  }}
                />

                <TextField
                  label="Resumo Profissional"
                  value={enrichData.summary}
                  onChange={(e) => setEnrichData({ ...enrichData, summary: e.target.value })}
                  fullWidth
                  multiline
                  rows={4}
                  placeholder="Resumo profissional do candidato..."
                />

                {/* Skills */}
                <Box>
                  <Typography variant="body2" fontWeight={500} gutterBottom>
                    Skills / Competencias
                  </Typography>
                  <Box display="flex" gap={1} mb={1}>
                    <TextField
                      size="small"
                      placeholder="Adicionar skill..."
                      value={skillInput}
                      onChange={(e) => setSkillInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && addSkill()}
                      fullWidth
                    />
                    <Button variant="outlined" onClick={addSkill} disabled={!skillInput.trim()}>
                      Adicionar
                    </Button>
                  </Box>
                  <Box display="flex" flexWrap="wrap" gap={0.5}>
                    {enrichData.skills?.map((skill) => (
                      <Chip
                        key={skill}
                        label={skill}
                        onDelete={() => removeSkill(skill)}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </Box>

                <Button
                  variant="contained"
                  onClick={handleManualEnrich}
                  disabled={enriching || !candidateId}
                  startIcon={enriching ? <CircularProgress size={18} color="inherit" /> : <LinkedIn />}
                  sx={{ alignSelf: 'flex-start' }}
                >
                  {enriching ? 'Enriquecendo...' : 'Salvar Enriquecimento'}
                </Button>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Dicas
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mt: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    - Use o ID do candidato da pagina de detalhes
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    - Adicione skills relevantes para melhorar a busca
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    - O headline ajuda no matching de vagas
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    - O resumo e indexado para busca semantica
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default LinkedInPage;
