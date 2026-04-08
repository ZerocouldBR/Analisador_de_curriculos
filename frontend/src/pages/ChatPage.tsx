import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Divider,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Send as SendIcon,
  Add as AddIcon,
  SmartToy as BotIcon,
  Person as PersonIcon,
  Work as WorkIcon,
  Delete as DeleteIcon,
  History as HistoryIcon,
  Lightbulb as SuggestionIcon,
  OpenInNew as OpenIcon,
  MenuOpen,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { ChatConversation, ChatMessage, ChatResponse } from '../types';
import { useNotification } from '../contexts/NotificationContext';

const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { showError } = useNotification();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  const [jobDialogOpen, setJobDialogOpen] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const convs = await apiService.getConversations();
      setConversations(convs);
    } catch (err) {
      console.error('Error loading conversations:', err);
    }
  };

  const createConversation = async (title?: string, jobDesc?: string, jobTtl?: string) => {
    try {
      const conv = await apiService.createConversation({
        title: title || 'Nova Conversa',
        job_description: jobDesc,
        job_title: jobTtl,
      });
      setConversations((prev) => [conv, ...prev]);
      setActiveConversation(conv);
      setMessages([]);
      setLastResponse(null);
      return conv;
    } catch (err: any) {
      showError(err.response?.data?.detail || 'Erro ao criar conversa');
      return null;
    }
  };

  const selectConversation = async (conv: ChatConversation) => {
    setActiveConversation(conv);
    setLastResponse(null);
    try {
      const msgs = await apiService.getMessages(conv.id);
      setMessages(msgs);
    } catch (err) {
      showError('Erro ao carregar mensagens');
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    let conv = activeConversation;
    if (!conv) {
      conv = await createConversation();
      if (!conv) return;
    }

    const userMessage = input.trim();
    setInput('');
    setLoading(true);

    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userMessage,
      tokens_used: 0,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await apiService.sendMessage(conv.id, userMessage);
      setLastResponse(response);

      const assistantMsg: ChatMessage = {
        id: response.message_id,
        role: 'assistant',
        content: response.message,
        tokens_used: response.tokens_used,
        created_at: new Date().toISOString(),
        metadata: {
          candidates_found: response.candidates_found.map((c) => c.id),
          chunks_used: response.sources.length,
          confidence: response.confidence,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
      loadConversations();
    } catch (err: any) {
      showError(err.response?.data?.detail || 'Erro ao enviar mensagem');
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setLoading(false);
    }
  };

  const handleJobAnalysis = async () => {
    if (!jobDescription.trim()) return;
    setJobDialogOpen(false);
    setLoading(true);

    try {
      let conv = activeConversation;
      if (!conv) {
        conv = await createConversation(`Analise: ${jobTitle || 'Vaga'}`, jobDescription, jobTitle);
        if (!conv) return;
      }

      const response = await apiService.analyzeJob(conv.id, jobDescription, jobTitle);
      setLastResponse(response);

      const userMsg: ChatMessage = {
        id: Date.now(),
        role: 'user',
        content: `Analise a vaga: ${jobTitle}\n\n${jobDescription}`,
        tokens_used: 0,
        created_at: new Date().toISOString(),
      };
      const assistantMsg: ChatMessage = {
        id: response.message_id,
        role: 'assistant',
        content: response.message,
        tokens_used: response.tokens_used,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      loadConversations();
    } catch (err: any) {
      showError(err.response?.data?.detail || 'Erro na analise');
    } finally {
      setLoading(false);
      setJobTitle('');
      setJobDescription('');
    }
  };

  const archiveConversation = async (convId: number) => {
    try {
      await apiService.archiveConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversation?.id === convId) {
        setActiveConversation(null);
        setMessages([]);
      }
    } catch (err) {
      showError('Erro ao arquivar conversa');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 120px)', mx: -3, mt: -3 }}>
      {/* Sidebar */}
      <Paper
        sx={{
          width: sidebarOpen ? 300 : 0,
          overflow: 'hidden',
          transition: 'width 0.3s',
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 0,
          borderRight: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box sx={{ p: 2, display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            fullWidth
            onClick={() => createConversation()}
            size="small"
          >
            Nova Conversa
          </Button>
          <Tooltip title="Analisar Vaga">
            <IconButton
              onClick={() => setJobDialogOpen(true)}
              color="primary"
              sx={{ border: '1px solid', borderColor: 'divider' }}
            >
              <WorkIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>

        <Divider />

        <List sx={{ flexGrow: 1, overflow: 'auto', px: 1 }}>
          {conversations.length === 0 ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Nenhuma conversa ainda
              </Typography>
            </Box>
          ) : (
            conversations.map((conv) => (
              <ListItem
                key={conv.id}
                disablePadding
                sx={{ mb: 0.5 }}
                secondaryAction={
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      archiveConversation(conv.id);
                    }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                }
              >
                <ListItemButton
                  selected={activeConversation?.id === conv.id}
                  onClick={() => selectConversation(conv)}
                  sx={{ borderRadius: 1.5 }}
                >
                  <ListItemText
                    primary={conv.title}
                    secondary={`${conv.message_count} msgs`}
                    primaryTypographyProps={{ noWrap: true, variant: 'body2', fontWeight: 500 }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItemButton>
              </ListItem>
            ))
          )}
        </List>
      </Paper>

      {/* Main Chat Area */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <Paper sx={{ p: 2, borderRadius: 0, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Box display="flex" alignItems="center" gap={1}>
              <IconButton onClick={() => setSidebarOpen(!sidebarOpen)} size="small">
                <MenuOpen sx={{ transform: sidebarOpen ? 'none' : 'scaleX(-1)' }} />
              </IconButton>
              <Box>
                <Typography variant="subtitle1" fontWeight={600}>
                  {activeConversation?.title || 'Chat de Analise de Curriculos'}
                </Typography>
                {activeConversation?.job_title && (
                  <Chip
                    label={`Vaga: ${activeConversation.job_title}`}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                )}
              </Box>
            </Box>
          </Box>
        </Paper>

        {/* Messages */}
        <Box sx={{ flexGrow: 1, overflow: 'auto', p: 3 }}>
          {messages.length === 0 ? (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                opacity: 0.7,
              }}
            >
              <BotIcon sx={{ fontSize: 72, mb: 2, color: 'primary.main', opacity: 0.6 }} />
              <Typography variant="h5" fontWeight={600} gutterBottom>
                Assistente de Recrutamento
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                align="center"
                sx={{ maxWidth: 500, mb: 3 }}
              >
                Faca perguntas sobre os curriculos da base, analise candidatos para vagas,
                compare profissionais ou busque por skills especificas.
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'center' }}>
                {[
                  'Quais candidatos tem experiencia com SAP?',
                  'Liste operadores de CNC disponiveis',
                  'Quem possui NR-12 e NR-35?',
                  'Compare os candidatos mais qualificados',
                ].map((suggestion, i) => (
                  <Chip
                    key={i}
                    label={suggestion}
                    onClick={() => setInput(suggestion)}
                    variant="outlined"
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.08) },
                    }}
                  />
                ))}
              </Box>
            </Box>
          ) : (
            messages.map((msg) => (
              <Box
                key={msg.id}
                sx={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  mb: 2.5,
                }}
              >
                <Paper
                  sx={{
                    p: 2.5,
                    maxWidth: '75%',
                    backgroundColor:
                      msg.role === 'user'
                        ? 'primary.main'
                        : theme.palette.mode === 'light'
                        ? 'grey.50'
                        : 'grey.900',
                    color: msg.role === 'user' ? 'primary.contrastText' : 'text.primary',
                    borderRadius: 3,
                    borderTopRightRadius: msg.role === 'user' ? 4 : 24,
                    borderTopLeftRadius: msg.role === 'user' ? 24 : 4,
                    border: msg.role === 'assistant' ? '1px solid' : 'none',
                    borderColor: 'divider',
                  }}
                >
                  <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                    {msg.role === 'user' ? (
                      <PersonIcon sx={{ fontSize: 16 }} />
                    ) : (
                      <BotIcon sx={{ fontSize: 16 }} />
                    )}
                    <Typography variant="caption" fontWeight={600}>
                      {msg.role === 'user' ? 'Voce' : 'Assistente IA'}
                    </Typography>
                  </Box>
                  <Typography
                    variant="body2"
                    sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6 }}
                  >
                    {msg.content}
                  </Typography>
                  {msg.metadata?.confidence !== undefined && msg.metadata.confidence > 0 && (
                    <Chip
                      label={`Confianca: ${(msg.metadata.confidence * 100).toFixed(0)}%`}
                      size="small"
                      sx={{ mt: 1.5 }}
                      variant="outlined"
                      color={msg.metadata.confidence > 0.7 ? 'success' : 'warning'}
                    />
                  )}
                </Paper>
              </Box>
            ))
          )}

          {loading && (
            <Box display="flex" alignItems="center" gap={1.5} sx={{ mb: 2 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Analisando curriculos...
              </Typography>
            </Box>
          )}

          <div ref={messagesEndRef} />
        </Box>

        {/* Suggestions */}
        {lastResponse && lastResponse.suggestions.length > 0 && (
          <Box sx={{ px: 3, pb: 1, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <SuggestionIcon fontSize="small" color="action" />
            {lastResponse.suggestions.map((suggestion, i) => (
              <Chip
                key={i}
                label={suggestion}
                size="small"
                variant="outlined"
                onClick={() => setInput(suggestion)}
                sx={{ cursor: 'pointer' }}
              />
            ))}
          </Box>
        )}

        {/* Candidates Found */}
        {lastResponse && lastResponse.candidates_found.length > 0 && (
          <Box sx={{ px: 3, pb: 1 }}>
            <Typography variant="caption" color="text.secondary" fontWeight={500}>
              Candidatos encontrados:
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
              {lastResponse.candidates_found.slice(0, 5).map((candidate) => (
                <Chip
                  key={candidate.id}
                  label={`${candidate.name} (${(candidate.relevance * 100).toFixed(0)}%)`}
                  size="small"
                  color="primary"
                  variant="outlined"
                  onClick={() => navigate(`/candidates/${candidate.id}`)}
                  onDelete={() => navigate(`/candidates/${candidate.id}`)}
                  deleteIcon={<OpenIcon fontSize="small" />}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Input Area */}
        <Paper
          sx={{
            p: 2,
            borderRadius: 0,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box display="flex" gap={1} alignItems="flex-end">
            <TextField
              fullWidth
              multiline
              maxRows={4}
              placeholder="Pergunte sobre os curriculos, analise candidatos para vagas..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
              size="small"
              sx={{
                '& .MuiOutlinedInput-root': { borderRadius: 3 },
              }}
            />
            <Button
              variant="contained"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              sx={{ minWidth: 50, height: 40, borderRadius: 3 }}
            >
              <SendIcon fontSize="small" />
            </Button>
          </Box>
        </Paper>
      </Box>

      {/* Job Analysis Dialog */}
      <Dialog open={jobDialogOpen} onClose={() => setJobDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle fontWeight={600}>Analisar Oportunidade de Emprego</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Descreva a vaga e o sistema buscara os melhores candidatos na base de curriculos.
          </Typography>
          <TextField
            fullWidth
            label="Titulo da Vaga"
            placeholder="Ex: Operador de Producao - CNC"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            multiline
            rows={8}
            label="Descricao da Vaga"
            placeholder="Descreva requisitos, responsabilidades, qualificacoes necessarias..."
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setJobDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleJobAnalysis}
            disabled={!jobDescription.trim()}
            startIcon={<WorkIcon />}
          >
            Analisar Candidatos
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ChatPage;
