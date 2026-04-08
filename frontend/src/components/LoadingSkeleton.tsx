import React from 'react';
import { Box, Skeleton, Grid, Paper } from '@mui/material';

export const DashboardSkeleton: React.FC = () => (
  <Box>
    <Skeleton variant="text" width={200} height={40} sx={{ mb: 2 }} />
    <Grid container spacing={3} sx={{ mb: 3 }}>
      {[1, 2, 3, 4].map((i) => (
        <Grid item xs={12} sm={6} md={3} key={i}>
          <Paper sx={{ p: 3 }}>
            <Skeleton variant="text" width={100} />
            <Skeleton variant="text" width={60} height={48} />
          </Paper>
        </Grid>
      ))}
    </Grid>
    <Grid container spacing={3}>
      <Grid item xs={12} md={8}>
        <Paper sx={{ p: 3, height: 300 }}>
          <Skeleton variant="text" width={150} sx={{ mb: 2 }} />
          <Skeleton variant="rectangular" height={220} />
        </Paper>
      </Grid>
      <Grid item xs={12} md={4}>
        <Paper sx={{ p: 3, height: 300 }}>
          <Skeleton variant="text" width={150} sx={{ mb: 2 }} />
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} variant="text" sx={{ mb: 1 }} />
          ))}
        </Paper>
      </Grid>
    </Grid>
  </Box>
);

export const TableSkeleton: React.FC = () => (
  <Box>
    <Box display="flex" justifyContent="space-between" mb={3}>
      <Skeleton variant="text" width={200} height={40} />
      <Skeleton variant="rectangular" width={150} height={36} sx={{ borderRadius: 1 }} />
    </Box>
    <Paper sx={{ p: 2 }}>
      <Skeleton variant="rectangular" height={50} sx={{ mb: 1 }} />
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <Skeleton key={i} variant="rectangular" height={52} sx={{ mb: 0.5 }} />
      ))}
    </Paper>
  </Box>
);

export const DetailSkeleton: React.FC = () => (
  <Box>
    <Skeleton variant="text" width={100} height={36} sx={{ mb: 1 }} />
    <Skeleton variant="text" width={300} height={48} sx={{ mb: 3 }} />
    <Grid container spacing={3}>
      <Grid item xs={12} md={8}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Skeleton variant="text" width={200} sx={{ mb: 2 }} />
          <Grid container spacing={2}>
            {[1, 2, 3, 4].map((i) => (
              <Grid item xs={12} sm={6} key={i}>
                <Skeleton variant="text" />
              </Grid>
            ))}
          </Grid>
        </Paper>
        <Paper sx={{ p: 3 }}>
          <Skeleton variant="text" width={150} sx={{ mb: 2 }} />
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rectangular" height={60} sx={{ mb: 1, borderRadius: 1 }} />
          ))}
        </Paper>
      </Grid>
      <Grid item xs={12} md={4}>
        <Paper sx={{ p: 3 }}>
          <Skeleton variant="text" width={150} sx={{ mb: 2 }} />
          <Skeleton variant="text" />
          <Skeleton variant="text" width={80} height={48} />
        </Paper>
      </Grid>
    </Grid>
  </Box>
);

export const ChatSkeleton: React.FC = () => (
  <Box sx={{ display: 'flex', height: '100%' }}>
    <Box sx={{ width: 300, p: 2 }}>
      <Skeleton variant="rectangular" height={36} sx={{ mb: 2, borderRadius: 1 }} />
      {[1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} variant="rectangular" height={48} sx={{ mb: 1, borderRadius: 1 }} />
      ))}
    </Box>
    <Box sx={{ flexGrow: 1, p: 2 }}>
      <Skeleton variant="rectangular" height={50} sx={{ mb: 2, borderRadius: 1 }} />
      <Box sx={{ flexGrow: 1 }}>
        {[1, 2, 3].map((i) => (
          <Box key={i} display="flex" justifyContent={i % 2 ? 'flex-end' : 'flex-start'} mb={2}>
            <Skeleton
              variant="rectangular"
              width={i % 2 ? '40%' : '60%'}
              height={80}
              sx={{ borderRadius: 2 }}
            />
          </Box>
        ))}
      </Box>
    </Box>
  </Box>
);
