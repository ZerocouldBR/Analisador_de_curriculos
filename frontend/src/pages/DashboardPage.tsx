import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  Chip,
  IconButton,
  Tooltip,
  useTheme,
  alpha,
  Button,
} from '@mui/material';
import {
  People,
  Description,
  TrendingUp,
  CheckCircle,
  ArrowForward,
  Refresh,
  SmartToy,
  Search,
  CloudUpload,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from 'recharts';
import { apiService } from '../services/api';
import { Candidate } from '../types';
import { DashboardSkeleton } from '../components/LoadingSkeleton';
import { useNotification } from '../contexts/NotificationContext';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactElement;
  color: string;
  trend?: string;
  onClick?: () => void;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color, trend, onClick }) => {
  const theme = useTheme();
  return (
    <Card
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': onClick
          ? { transform: 'translateY(-2px)', boxShadow: theme.shadows[4] }
          : {},
      }}
      onClick={onClick}
    >
      <CardContent sx={{ p: 3 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={500} gutterBottom>
              {title}
            </Typography>
            <Typography variant="h3" fontWeight={700}>
              {value}
            </Typography>
            {trend && (
              <Chip
                label={trend}
                size="small"
                color="success"
                variant="outlined"
                sx={{ mt: 1, fontSize: '0.7rem' }}
              />
            )}
          </Box>
          <Box
            sx={{
              backgroundColor: alpha(color, 0.12),
              borderRadius: 3,
              p: 1.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {React.cloneElement(icon, { sx: { fontSize: 32, color } })}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

const CHART_COLORS = ['#1565c0', '#2e7d32', '#ed6c02', '#9c27b0', '#d32f2f', '#0288d1', '#f57c00', '#7b1fa2'];

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { showError } = useNotification();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalCandidates: 0,
    totalDocuments: 0,
    recentUploads: 0,
    processedToday: 0,
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      const candidatesData = await apiService.getCandidates();
      setCandidates(candidatesData);

      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const weekAgo = new Date(today);
      weekAgo.setDate(weekAgo.getDate() - 7);

      const recentCandidates = candidatesData.filter(
        (c) => new Date(c.created_at) >= today
      );
      const weekCandidates = candidatesData.filter(
        (c) => new Date(c.created_at) >= weekAgo
      );

      setStats({
        totalCandidates: candidatesData.length,
        totalDocuments: candidatesData.length,
        recentUploads: weekCandidates.length,
        processedToday: recentCandidates.length,
      });
    } catch (error) {
      showError('Erro ao carregar dados do dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <DashboardSkeleton />;

  // Build chart data from candidates
  const stateCount: Record<string, number> = {};
  candidates.forEach((c) => {
    const st = c.state || 'N/A';
    stateCount[st] = (stateCount[st] || 0) + 1;
  });
  const stateData = Object.entries(stateCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));

  const monthCount: Record<string, number> = {};
  candidates.forEach((c) => {
    const date = new Date(c.created_at);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    monthCount[key] = (monthCount[key] || 0) + 1;
  });
  const monthData = Object.entries(monthCount)
    .sort()
    .slice(-6)
    .map(([month, count]) => ({
      month: month.split('-')[1] + '/' + month.split('-')[0].slice(2),
      count,
    }));

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Visao geral do sistema de analise de curriculos
          </Typography>
        </Box>
        <Tooltip title="Atualizar dados">
          <IconButton onClick={fetchData}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Stat Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total de Candidatos"
            value={stats.totalCandidates}
            icon={<People />}
            color={theme.palette.primary.main}
            onClick={() => navigate('/candidates')}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total de Documentos"
            value={stats.totalDocuments}
            icon={<Description />}
            color={theme.palette.success.main}
            onClick={() => navigate('/upload')}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Uploads na Semana"
            value={stats.recentUploads}
            icon={<TrendingUp />}
            color={theme.palette.warning.main}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Processados Hoje"
            value={stats.processedToday}
            icon={<CheckCircle />}
            color={theme.palette.secondary.main}
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Cadastros por Mes
            </Typography>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={monthData}>
                <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <RechartsTooltip />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke={theme.palette.primary.main}
                  fill={alpha(theme.palette.primary.main, 0.15)}
                  strokeWidth={2}
                  name="Candidatos"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Candidatos por Estado
            </Typography>
            {stateData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={stateData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {stateData.map((_, index) => (
                      <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Box display="flex" alignItems="center" justifyContent="center" height={280}>
                <Typography color="text.secondary">Sem dados disponiveis</Typography>
              </Box>
            )}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
              {stateData.map((item, i) => (
                <Chip
                  key={item.name}
                  label={`${item.name}: ${item.value}`}
                  size="small"
                  sx={{
                    bgcolor: alpha(CHART_COLORS[i % CHART_COLORS.length], 0.12),
                    color: CHART_COLORS[i % CHART_COLORS.length],
                    fontWeight: 500,
                    fontSize: '0.7rem',
                  }}
                />
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* Quick actions + Recent candidates */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Acoes Rapidas
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<CloudUpload />}
                onClick={() => navigate('/upload')}
                sx={{ justifyContent: 'flex-start', py: 1.2 }}
              >
                Upload de Curriculos
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<Search />}
                onClick={() => navigate('/search')}
                sx={{ justifyContent: 'flex-start', py: 1.2 }}
              >
                Busca Inteligente
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<SmartToy />}
                onClick={() => navigate('/chat')}
                sx={{ justifyContent: 'flex-start', py: 1.2 }}
              >
                Chat com IA
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<People />}
                onClick={() => navigate('/candidates')}
                sx={{ justifyContent: 'flex-start', py: 1.2 }}
              >
                Gerenciar Candidatos
              </Button>
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6" fontWeight={600}>
                Candidatos Recentes
              </Typography>
              <Button
                size="small"
                endIcon={<ArrowForward />}
                onClick={() => navigate('/candidates')}
              >
                Ver todos
              </Button>
            </Box>
            {candidates.length === 0 ? (
              <Box textAlign="center" py={4}>
                <People sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                <Typography color="text.secondary">
                  Nenhum candidato cadastrado ainda
                </Typography>
                <Button
                  variant="contained"
                  size="small"
                  sx={{ mt: 2 }}
                  onClick={() => navigate('/upload')}
                >
                  Fazer primeiro upload
                </Button>
              </Box>
            ) : (
              candidates.slice(0, 6).map((candidate) => (
                <Box
                  key={candidate.id}
                  sx={{
                    py: 1.5,
                    px: 2,
                    borderRadius: 1.5,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'background-color 0.15s',
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                  onClick={() => navigate(`/candidates/${candidate.id}`)}
                >
                  <Box>
                    <Typography variant="body2" fontWeight={600}>
                      {candidate.full_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {candidate.email || 'Sem email'} {candidate.city ? `- ${candidate.city}/${candidate.state}` : ''}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(candidate.created_at).toLocaleDateString('pt-BR')}
                  </Typography>
                </Box>
              ))
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;
