import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Paper,
  Typography,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Tooltip,
  Chip,
  InputAdornment,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import {
  Add,
  Edit,
  Delete,
  Visibility,
  Search,
  FilterList,
  Refresh,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Candidate } from '../types';
import { useNotification } from '../contexts/NotificationContext';
import { TableSkeleton } from '../components/LoadingSkeleton';

const CandidatesPage: React.FC = () => {
  const navigate = useNavigate();
  const { showSuccess, showError } = useNotification();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [filteredCandidates, setFilteredCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingCandidate, setEditingCandidate] = useState<Candidate | null>(null);
  const [searchText, setSearchText] = useState('');
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    doc_id: '',
    city: '',
    state: '',
    address: '',
  });

  useEffect(() => {
    fetchCandidates();
  }, []);

  useEffect(() => {
    if (searchText) {
      const lower = searchText.toLowerCase();
      setFilteredCandidates(
        candidates.filter(
          (c) =>
            c.full_name.toLowerCase().includes(lower) ||
            (c.email?.toLowerCase().includes(lower)) ||
            (c.city?.toLowerCase().includes(lower)) ||
            (c.phone?.includes(searchText))
        )
      );
    } else {
      setFilteredCandidates(candidates);
    }
  }, [searchText, candidates]);

  const fetchCandidates = async () => {
    try {
      setLoading(true);
      const data = await apiService.getCandidates();
      setCandidates(data);
      setFilteredCandidates(data);
    } catch (error) {
      showError('Erro ao carregar candidatos');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (candidate?: Candidate) => {
    if (candidate) {
      setEditingCandidate(candidate);
      setFormData({
        full_name: candidate.full_name,
        email: candidate.email || '',
        phone: candidate.phone || '',
        doc_id: candidate.doc_id || '',
        city: candidate.city || '',
        state: candidate.state || '',
        address: candidate.address || '',
      });
    } else {
      setEditingCandidate(null);
      setFormData({ full_name: '', email: '', phone: '', doc_id: '', city: '', state: '', address: '' });
    }
    setOpenDialog(true);
  };

  const handleSubmit = async () => {
    if (!formData.full_name.trim()) {
      showError('Nome completo e obrigatorio');
      return;
    }
    try {
      if (editingCandidate) {
        await apiService.updateCandidate(editingCandidate.id, formData);
        showSuccess('Candidato atualizado com sucesso');
      } else {
        await apiService.createCandidate(formData);
        showSuccess('Candidato criado com sucesso');
      }
      setOpenDialog(false);
      setEditingCandidate(null);
      fetchCandidates();
    } catch (error) {
      showError('Erro ao salvar candidato');
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (window.confirm(`Tem certeza que deseja excluir "${name}"? Esta acao nao pode ser desfeita.`)) {
      try {
        await apiService.deleteCandidate(id);
        showSuccess('Candidato excluido com sucesso');
        fetchCandidates();
      } catch (error) {
        showError('Erro ao excluir candidato');
      }
    }
  };

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70, headerAlign: 'center', align: 'center' },
    {
      field: 'full_name',
      headerName: 'Nome',
      flex: 1,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => (
        <Typography variant="body2" fontWeight={500}>
          {params.value}
        </Typography>
      ),
    },
    { field: 'email', headerName: 'Email', flex: 1, minWidth: 180 },
    { field: 'phone', headerName: 'Telefone', width: 140 },
    {
      field: 'city',
      headerName: 'Cidade',
      width: 130,
      renderCell: (params: GridRenderCellParams) =>
        params.value ? (
          <Chip label={params.value} size="small" variant="outlined" />
        ) : (
          <Typography variant="body2" color="text.disabled">-</Typography>
        ),
    },
    {
      field: 'state',
      headerName: 'UF',
      width: 70,
      headerAlign: 'center',
      align: 'center',
    },
    {
      field: 'created_at',
      headerName: 'Cadastro',
      width: 110,
      renderCell: (params: GridRenderCellParams) =>
        new Date(params.value).toLocaleDateString('pt-BR'),
    },
    {
      field: 'actions',
      headerName: 'Acoes',
      width: 140,
      sortable: false,
      headerAlign: 'center',
      align: 'center',
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          <Tooltip title="Ver detalhes">
            <IconButton size="small" onClick={() => navigate(`/candidates/${params.row.id}`)}>
              <Visibility fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Editar">
            <IconButton size="small" onClick={() => handleOpenDialog(params.row as Candidate)}>
              <Edit fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Excluir">
            <IconButton
              size="small"
              onClick={() => handleDelete(params.row.id, params.row.full_name)}
              sx={{ color: 'error.main' }}
            >
              <Delete fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) return <TableSkeleton />;

  return (
    <Box className="fade-in">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Candidatos
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {candidates.length} candidato(s) cadastrado(s)
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title="Atualizar">
            <IconButton onClick={fetchCandidates}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button variant="contained" startIcon={<Add />} onClick={() => handleOpenDialog()}>
            Novo Candidato
          </Button>
        </Box>
      </Box>

      {/* Search bar */}
      <Paper sx={{ p: 2, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <TextField
          fullWidth
          placeholder="Buscar por nome, email, cidade ou telefone..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search color="action" />
              </InputAdornment>
            ),
          }}
        />
      </Paper>

      {/* Data Grid */}
      <Paper sx={{ height: 600, border: '1px solid', borderColor: 'divider' }}>
        <DataGrid
          rows={filteredCandidates}
          columns={columns}
          pageSizeOptions={[10, 25, 50, 100]}
          initialState={{
            pagination: { paginationModel: { pageSize: 25 } },
            sorting: { sortModel: [{ field: 'created_at', sort: 'desc' }] },
          }}
          disableRowSelectionOnClick
          sx={{
            '& .MuiDataGrid-row:hover': { bgcolor: 'action.hover' },
          }}
        />
      </Paper>

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle fontWeight={600}>
          {editingCandidate ? 'Editar Candidato' : 'Novo Candidato'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Nome Completo"
              fullWidth
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              required
              autoFocus
            />
            <Box display="flex" gap={2}>
              <TextField
                label="Email"
                type="email"
                fullWidth
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              />
              <TextField
                label="Telefone"
                fullWidth
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
            </Box>
            <TextField
              label="CPF"
              fullWidth
              value={formData.doc_id}
              onChange={(e) => setFormData({ ...formData, doc_id: e.target.value })}
            />
            <TextField
              label="Endereco"
              fullWidth
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
            />
            <Box display="flex" gap={2}>
              <TextField
                label="Cidade"
                fullWidth
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
              />
              <TextField
                label="Estado (UF)"
                sx={{ width: 150 }}
                value={formData.state}
                onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                inputProps={{ maxLength: 2 }}
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOpenDialog(false)}>Cancelar</Button>
          <Button onClick={handleSubmit} variant="contained">
            Salvar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CandidatesPage;
