import React, { useEffect, useState } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  CircularProgress,
} from '@mui/material';
import {
  People,
  Description,
  TrendingUp,
  CheckCircle,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Candidate } from '../types';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactElement;
  color: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color }) => (
  <Card>
    <CardContent>
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <Box>
          <Typography color="textSecondary" gutterBottom variant="body2">
            {title}
          </Typography>
          <Typography variant="h4">{value}</Typography>
        </Box>
        <Box
          sx={{
            backgroundColor: color,
            borderRadius: '50%',
            p: 2,
            color: 'white',
          }}
        >
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

const DashboardPage: React.FC = () => {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalCandidates: 0,
    totalDocuments: 0,
    recentUploads: 0,
    processedToday: 0,
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const candidatesData = await apiService.getCandidates();
        setCandidates(candidatesData);

        // Calculate stats
        const totalCandidates = candidatesData.length;
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const recentCandidates = candidatesData.filter(
          (c) => new Date(c.created_at) >= today
        );

        setStats({
          totalCandidates,
          totalDocuments: totalCandidates, // Simplified - would need separate API call
          recentUploads: recentCandidates.length,
          processedToday: recentCandidates.length,
        });
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total de Candidatos"
            value={stats.totalCandidates}
            icon={<People />}
            color="#1976d2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total de Documentos"
            value={stats.totalDocuments}
            icon={<Description />}
            color="#2e7d32"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Uploads Recentes"
            value={stats.recentUploads}
            icon={<TrendingUp />}
            color="#ed6c02"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Processados Hoje"
            value={stats.processedToday}
            icon={<CheckCircle />}
            color="#9c27b0"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Candidatos Recentes
            </Typography>
            {candidates.slice(0, 5).map((candidate) => (
              <Box
                key={candidate.id}
                sx={{
                  py: 1,
                  borderBottom: '1px solid #eee',
                  '&:last-child': { borderBottom: 'none' },
                }}
              >
                <Typography variant="body1">{candidate.full_name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {candidate.email || 'Sem email'}
                </Typography>
              </Box>
            ))}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Atividades Recentes
            </Typography>
            <Box sx={{ py: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Sistema em operação normal
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;
