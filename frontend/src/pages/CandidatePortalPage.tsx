import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  AlertTitle,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  Paper,
  TextField,
  ThemeProvider,
  Typography,
  createTheme,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import {
  AutoAwesome,
  Cancel,
  Check,
  Edit,
  Save,
  Work,
  Person,
  Email,
  Phone,
  LocationOn,
  LinkedIn,
  GitHub,
  Link as LinkIcon,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { ImproveResponse, PortalExperience, PortalProfile } from '../types';
import PortalJobsSection from '../components/PortalJobsSection';

/**
 * Portal publico do candidato (magic link).
 * Acessivel em /me/:token sem autenticacao.
 */
const CandidatePortalPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<PortalProfile>>({});
  const [experienceDrafts, setExperienceDrafts] = useState<Record<number, PortalExperience>>({});
  const [editingExpIndex, setEditingExpIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  // Suggestion dialog state
  const [suggestion, setSuggestion] = useState<ImproveResponse | null>(null);
  const [loadingSuggestion, setLoadingSuggestion] = useState(false);

  useEffect(() => {
    if (!token) return;
    apiService
      .getPortalProfile(token)
      .then((p) => setProfile(p))
      .catch((err: any) => {
        setError(err?.response?.data?.detail || 'Link invalido ou expirado');
      })
      .finally(() => setLoading(false));
  }, [token]);

  const brandColor = profile?.company?.brand_color || '#1976d2';
  const pageTheme = createTheme({ palette: { primary: { main: brandColor } } });

  const startEditing = (field: string) => {
    if (!profile) return;
    setEditingField(field);
    setEditValues({
      full_name: profile.full_name,
      email: profile.email,
      phone: profile.phone,
      location: profile.location,
      linkedin: profile.linkedin,
      github: profile.github,
      portfolio: profile.portfolio,
      headline: profile.headline,
      summary: profile.summary,
      skills_technical: profile.skills_technical,
    });
  };

  const cancelEditing = () => {
    setEditingField(null);
    setEditValues({});
  };

  const saveField = async (field: keyof PortalProfile) => {
    if (!token) return;
    try {
      setSaving(true);
      const updated = await apiService.patchPortalProfile(token, {
        [field]: editValues[field],
      } as any);
      setProfile(updated);
      setEditingField(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  };

  const saveExperience = async (index: number) => {
    if (!token || !profile) return;
    const draft = experienceDrafts[index];
    if (!draft) {
      setEditingExpIndex(null);
      return;
    }
    const updatedExps = [...profile.experiences];
    updatedExps[index] = { ...(updatedExps[index] || {}), ...draft };
    try {
      setSaving(true);
      const updated = await apiService.patchPortalProfile(token, { experiences: updatedExps });
      setProfile(updated);
      setEditingExpIndex(null);
      setExperienceDrafts((d) => {
        const nd = { ...d };
        delete nd[index];
        return nd;
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao salvar experiencia');
    } finally {
      setSaving(false);
    }
  };

  const requestSuggestion = async (field: 'summary' | 'headline' | 'experience', index?: number) => {
    if (!token) return;
    try {
      setLoadingSuggestion(true);
      const res = await apiService.improvePortalField(token, field, index);
      setSuggestion(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao gerar sugestao');
    } finally {
      setLoadingSuggestion(false);
    }
  };

  const applySuggestion = async () => {
    if (!token || !suggestion || !suggestion.suggestion) return;
    try {
      setSaving(true);
      let value: any;
      if (suggestion.field === 'summary') {
        value = suggestion.suggestion.improved_summary;
      } else if (suggestion.field === 'headline') {
        value = suggestion.suggestion.improved_headline;
      } else if (suggestion.field === 'experience') {
        value = {
          description:
            suggestion.suggestion.improved_description ||
            (suggestion.suggestion.improved_bullets || []).join('\n'),
        };
      }
      if (value == null) return;
      const updated = await apiService.applyPortalSuggestion(
        token,
        suggestion.field as any,
        value,
        suggestion.experience_index,
      );
      setProfile(updated);
      setSuggestion(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Erro ao aplicar sugestao');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !profile) {
    return (
      <Container maxWidth="sm" sx={{ py: 8 }}>
        <Alert severity="error">
          <AlertTitle>Link invalido</AlertTitle>
          {error || 'Nao foi possivel carregar seu perfil'}
        </Alert>
      </Container>
    );
  }

  const brand = profile.company;

  return (
    <ThemeProvider theme={pageTheme}>
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
        <Box sx={{ bgcolor: brandColor, color: '#fff', py: 3 }}>
          <Container maxWidth="md">
            <Box display="flex" alignItems="center" gap={2}>
              {brand?.logo_url && (
                <Avatar
                  src={brand.logo_url.startsWith('http') ? brand.logo_url : undefined}
                  sx={{ bgcolor: 'rgba(255,255,255,0.2)' }}
                />
              )}
              <Box flexGrow={1}>
                <Typography variant="h6">{brand?.name || 'Perfil do candidato'}</Typography>
                <Typography variant="caption" sx={{ opacity: 0.9 }}>
                  Voce pode editar seu perfil e pedir sugestoes de melhoria via IA.
                  {profile.token_expires_at && (
                    <> Link valido ate {new Date(profile.token_expires_at).toLocaleString('pt-BR')}</>
                  )}
                </Typography>
              </Box>
            </Box>
          </Container>
        </Box>

        <Container maxWidth="md" sx={{ py: 4 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {/* Dados basicos */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box display="flex" alignItems="center" gap={2} mb={2}>
              <Avatar
                src={profile.photo_url || undefined}
                sx={{ width: 64, height: 64 }}
              >
                {profile.full_name?.charAt(0).toUpperCase()}
              </Avatar>
              <Box flexGrow={1}>
                {editingField === 'basic' ? (
                  <Box display="flex" flexDirection="column" gap={1}>
                    <TextField
                      label="Nome completo"
                      size="small"
                      value={editValues.full_name || ''}
                      onChange={(e) => setEditValues({ ...editValues, full_name: e.target.value })}
                    />
                  </Box>
                ) : (
                  <>
                    <Typography variant="h5" fontWeight={700}>
                      {profile.full_name}
                    </Typography>
                  </>
                )}
              </Box>
              {editingField === 'basic' ? (
                <Box display="flex" gap={1}>
                  <IconButton onClick={cancelEditing}>
                    <Cancel />
                  </IconButton>
                  <IconButton color="primary" onClick={() => saveField('full_name')} disabled={saving}>
                    <Save />
                  </IconButton>
                </Box>
              ) : (
                <IconButton onClick={() => startEditing('basic')}>
                  <Edit />
                </IconButton>
              )}
            </Box>

            {/* Headline */}
            <FieldRow
              label="Titulo profissional (headline)"
              icon={<Work fontSize="small" />}
              editing={editingField === 'headline'}
              value={profile.headline}
              inputValue={editValues.headline || ''}
              onInputChange={(v) => setEditValues({ ...editValues, headline: v })}
              onStartEdit={() => startEditing('headline')}
              onCancel={cancelEditing}
              onSave={() => saveField('headline')}
              onImprove={() => requestSuggestion('headline')}
              saving={saving}
              loadingSuggestion={loadingSuggestion}
            />

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FieldRow
                  label="Email"
                  icon={<Email fontSize="small" />}
                  editing={editingField === 'email'}
                  value={profile.email}
                  inputValue={editValues.email || ''}
                  onInputChange={(v) => setEditValues({ ...editValues, email: v })}
                  onStartEdit={() => startEditing('email')}
                  onCancel={cancelEditing}
                  onSave={() => saveField('email')}
                  saving={saving}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FieldRow
                  label="Telefone"
                  icon={<Phone fontSize="small" />}
                  editing={editingField === 'phone'}
                  value={profile.phone}
                  inputValue={editValues.phone || ''}
                  onInputChange={(v) => setEditValues({ ...editValues, phone: v })}
                  onStartEdit={() => startEditing('phone')}
                  onCancel={cancelEditing}
                  onSave={() => saveField('phone')}
                  saving={saving}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FieldRow
                  label="Localizacao"
                  icon={<LocationOn fontSize="small" />}
                  editing={editingField === 'location'}
                  value={profile.location}
                  inputValue={editValues.location || ''}
                  onInputChange={(v) => setEditValues({ ...editValues, location: v })}
                  onStartEdit={() => startEditing('location')}
                  onCancel={cancelEditing}
                  onSave={() => saveField('location')}
                  saving={saving}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FieldRow
                  label="LinkedIn"
                  icon={<LinkedIn fontSize="small" />}
                  editing={editingField === 'linkedin'}
                  value={profile.linkedin}
                  inputValue={editValues.linkedin || ''}
                  onInputChange={(v) => setEditValues({ ...editValues, linkedin: v })}
                  onStartEdit={() => startEditing('linkedin')}
                  onCancel={cancelEditing}
                  onSave={() => saveField('linkedin')}
                  saving={saving}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FieldRow
                  label="GitHub"
                  icon={<GitHub fontSize="small" />}
                  editing={editingField === 'github'}
                  value={profile.github}
                  inputValue={editValues.github || ''}
                  onInputChange={(v) => setEditValues({ ...editValues, github: v })}
                  onStartEdit={() => startEditing('github')}
                  onCancel={cancelEditing}
                  onSave={() => saveField('github')}
                  saving={saving}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FieldRow
                  label="Portfolio"
                  icon={<LinkIcon fontSize="small" />}
                  editing={editingField === 'portfolio'}
                  value={profile.portfolio}
                  inputValue={editValues.portfolio || ''}
                  onInputChange={(v) => setEditValues({ ...editValues, portfolio: v })}
                  onStartEdit={() => startEditing('portfolio')}
                  onCancel={cancelEditing}
                  onSave={() => saveField('portfolio')}
                  saving={saving}
                />
              </Grid>
            </Grid>
          </Paper>

          {/* Resumo */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
              <Typography variant="subtitle1" fontWeight={600}>
                Resumo profissional
              </Typography>
              <Box display="flex" gap={1}>
                <Tooltip title="Sugerir melhoria com IA">
                  <span>
                    <Button
                      size="small"
                      startIcon={<AutoAwesome />}
                      onClick={() => requestSuggestion('summary')}
                      disabled={loadingSuggestion || !profile.summary}
                    >
                      Melhorar com IA
                    </Button>
                  </span>
                </Tooltip>
                {editingField === 'summary' ? (
                  <>
                    <IconButton onClick={cancelEditing}>
                      <Cancel />
                    </IconButton>
                    <IconButton color="primary" onClick={() => saveField('summary')} disabled={saving}>
                      <Save />
                    </IconButton>
                  </>
                ) : (
                  <IconButton onClick={() => startEditing('summary')}>
                    <Edit />
                  </IconButton>
                )}
              </Box>
            </Box>
            {editingField === 'summary' ? (
              <TextField
                value={editValues.summary || ''}
                onChange={(e) => setEditValues({ ...editValues, summary: e.target.value })}
                multiline
                minRows={4}
                fullWidth
              />
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                {profile.summary || 'Nao informado'}
              </Typography>
            )}
          </Paper>

          {/* Experiencias */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Experiencias ({profile.experiences.length})
            </Typography>
            {profile.experiences.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                Nenhuma experiencia cadastrada
              </Typography>
            )}
            {profile.experiences.map((exp, i) => {
              const isEditingThis = editingExpIndex === i;
              const draft = experienceDrafts[i] || exp;
              return (
                <Box key={i} sx={{ mb: 2, pb: 2, borderBottom: i < profile.experiences.length - 1 ? '1px solid' : 'none', borderColor: 'divider' }}>
                  <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Box>
                      <Typography variant="subtitle2" fontWeight={600}>
                        {exp.title || 'Cargo'} · {exp.company || 'Empresa'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {exp.start_date || '?'} — {exp.end_date || 'atual'}
                      </Typography>
                    </Box>
                    <Box display="flex" gap={1}>
                      <Tooltip title="Sugerir melhoria com IA">
                        <span>
                          <Button
                            size="small"
                            startIcon={<AutoAwesome />}
                            onClick={() => requestSuggestion('experience', i)}
                            disabled={loadingSuggestion || !exp.description}
                          >
                            Melhorar
                          </Button>
                        </span>
                      </Tooltip>
                      {isEditingThis ? (
                        <>
                          <IconButton onClick={() => setEditingExpIndex(null)}>
                            <Cancel />
                          </IconButton>
                          <IconButton color="primary" onClick={() => saveExperience(i)} disabled={saving}>
                            <Save />
                          </IconButton>
                        </>
                      ) : (
                        <IconButton
                          onClick={() => {
                            setEditingExpIndex(i);
                            setExperienceDrafts((d) => ({ ...d, [i]: { ...exp } }));
                          }}
                        >
                          <Edit />
                        </IconButton>
                      )}
                    </Box>
                  </Box>
                  {isEditingThis ? (
                    <TextField
                      value={draft.description || ''}
                      onChange={(e) =>
                        setExperienceDrafts((d) => ({
                          ...d,
                          [i]: { ...d[i], description: e.target.value },
                        }))
                      }
                      multiline
                      minRows={3}
                      fullWidth
                      sx={{ mt: 1 }}
                    />
                  ) : (
                    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', mt: 1 }}>
                      {exp.description || '(sem descricao)'}
                    </Typography>
                  )}
                </Box>
              );
            })}
          </Paper>

          {/* Skills */}
          {profile.skills_technical.length > 0 && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Skills tecnicas
              </Typography>
              <Box display="flex" gap={0.5} flexWrap="wrap">
                {profile.skills_technical.map((s) => (
                  <Chip key={s} label={s} size="small" />
                ))}
              </Box>
            </Paper>
          )}

          {/* Vagas e candidaturas (PR3) */}
          {token && <PortalJobsSection token={token} />}
        </Container>

        {/* Dialog de sugestao */}
        <Dialog
          open={!!suggestion}
          onClose={() => setSuggestion(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box display="flex" alignItems="center" gap={1}>
              <AutoAwesome color="primary" />
              Sugestao de melhoria
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            {!suggestion?.ai_available && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                IA indisponivel no momento. Tente mais tarde.
              </Alert>
            )}
            {suggestion?.error && !suggestion.suggestion && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {suggestion.error}
              </Alert>
            )}
            {suggestion?.original && (
              <Box mb={2}>
                <Typography variant="caption" color="text.secondary">
                  Versao atual
                </Typography>
                <Paper variant="outlined" sx={{ p: 1.5, mt: 0.5 }}>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {suggestion.original}
                  </Typography>
                </Paper>
              </Box>
            )}
            {suggestion?.suggestion && (
              <Box>
                <Typography variant="caption" color="primary">
                  Sugestao da IA
                </Typography>
                <Paper variant="outlined" sx={{ p: 1.5, mt: 0.5, borderColor: 'primary.main' }}>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {suggestion.suggestion.improved_summary ||
                      suggestion.suggestion.improved_headline ||
                      suggestion.suggestion.improved_description ||
                      (suggestion.suggestion.improved_bullets || []).join('\n')}
                  </Typography>
                </Paper>
                {suggestion.rationale && (
                  <Typography variant="caption" color="text.secondary" mt={1} display="block">
                    <strong>Motivo:</strong> {suggestion.rationale}
                  </Typography>
                )}
              </Box>
            )}
            {saving && <LinearProgress sx={{ mt: 2 }} />}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setSuggestion(null)}>Rejeitar</Button>
            <Button
              variant="contained"
              startIcon={<Check />}
              onClick={applySuggestion}
              disabled={!suggestion?.suggestion || saving}
            >
              Aprovar e aplicar
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </ThemeProvider>
  );
};

interface FieldRowProps {
  label: string;
  icon?: React.ReactElement;
  value?: string;
  editing: boolean;
  inputValue: string;
  onInputChange: (v: string) => void;
  onStartEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  saving?: boolean;
  onImprove?: () => void;
  loadingSuggestion?: boolean;
}

const FieldRow: React.FC<FieldRowProps> = ({
  label,
  icon,
  value,
  editing,
  inputValue,
  onInputChange,
  onStartEdit,
  onCancel,
  onSave,
  saving,
  onImprove,
  loadingSuggestion,
}) => (
  <Box display="flex" alignItems="center" gap={1} py={1}>
    {icon}
    <Box flexGrow={1}>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      {editing ? (
        <TextField
          size="small"
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          fullWidth
        />
      ) : (
        <Typography variant="body2">{value || 'Nao informado'}</Typography>
      )}
    </Box>
    {onImprove && !editing && (
      <Tooltip title="Sugerir com IA">
        <span>
          <IconButton size="small" onClick={onImprove} disabled={loadingSuggestion}>
            <AutoAwesome fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
    )}
    {editing ? (
      <>
        <IconButton size="small" onClick={onCancel}>
          <Cancel fontSize="small" />
        </IconButton>
        <IconButton size="small" color="primary" onClick={onSave} disabled={saving}>
          <Save fontSize="small" />
        </IconButton>
      </>
    ) : (
      <IconButton size="small" onClick={onStartEdit}>
        <Edit fontSize="small" />
      </IconButton>
    )}
  </Box>
);

export default CandidatePortalPage;
