# Frontend - Analisador de Currículos

Interface visual em React para o sistema de análise de currículos.

## 🚀 Tecnologias

- **React 18** - Framework JavaScript
- **TypeScript** - Tipagem estática
- **Material-UI (MUI)** - Componentes UI
- **React Router** - Navegação
- **Axios** - Cliente HTTP
- **WebSocket** - Atualizações em tempo real
- **React Dropzone** - Upload de arquivos

## 📁 Estrutura do Projeto

```
frontend/
├── public/              # Arquivos estáticos
├── src/
│   ├── components/      # Componentes reutilizáveis
│   │   └── Layout.tsx   # Layout principal com navegação
│   ├── contexts/        # Contextos React
│   │   └── AuthContext.tsx  # Gerenciamento de autenticação
│   ├── pages/           # Páginas da aplicação
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── CandidatesPage.tsx
│   │   ├── CandidateDetailPage.tsx
│   │   ├── SearchPage.tsx
│   │   ├── UploadPage.tsx
│   │   ├── SettingsPage.tsx
│   │   └── RolesPage.tsx
│   ├── services/        # Serviços de API
│   │   ├── api.ts       # Cliente HTTP para API REST
│   │   └── websocket.ts # Cliente WebSocket
│   ├── types/           # Definições TypeScript
│   │   └── index.ts     # Tipos e interfaces
│   ├── App.tsx          # Componente raiz
│   └── index.tsx        # Ponto de entrada
├── Dockerfile           # Container Docker
├── package.json         # Dependências npm
└── tsconfig.json        # Configuração TypeScript
```

## 🎨 Funcionalidades

### Autenticação
- ✅ Login com JWT
- ✅ Registro de novos usuários
- ✅ Logout
- ✅ Proteção de rotas

### Dashboard
- ✅ Estatísticas do sistema
- ✅ Candidatos recentes
- ✅ Métricas de upload

### Gerenciamento de Candidatos
- ✅ Listagem com DataGrid
- ✅ Criar novo candidato
- ✅ Editar candidato
- ✅ Excluir candidato
- ✅ Ver detalhes do candidato
- ✅ Visualizar documentos

### Upload de Currículos
- ✅ Drag & drop de arquivos
- ✅ Suporte a múltiplos formatos (PDF, DOCX, TXT, imagens)
- ✅ Progresso de upload em tempo real via WebSocket
- ✅ Associação com candidato existente ou criação automática
- ✅ Indicadores visuais de status

### Busca
- ✅ Busca semântica com embeddings
- ✅ Busca híbrida (semântica + texto completo)
- ✅ Exibição de trechos relevantes
- ✅ Score de relevância

### Administração
- ✅ Gerenciamento de funções (RBAC)
- ✅ Configuração de permissões
- ✅ Configurações do sistema
- ✅ Edição de prompts LLM

## 🛠️ Instalação e Execução

### Desenvolvimento Local

```bash
# Instalar dependências
npm install

# Iniciar servidor de desenvolvimento
npm start

# Acesse http://localhost:3000
```

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do frontend:

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

### Docker

```bash
# Build da imagem
docker build -t analisador-frontend .

# Executar container
docker run -p 3000:3000 analisador-frontend
```

### Docker Compose (Recomendado)

```bash
# Iniciar todos os serviços (backend + frontend + banco + redis + monitoring)
docker-compose up -d

# Frontend estará disponível em http://localhost:3000
```

## 📡 Integração com Backend

### API REST

O frontend se comunica com o backend via API REST:

```typescript
// Exemplo de uso do serviço de API
import { apiService } from './services/api';

// Login
const response = await apiService.login({ email, password });

// Listar candidatos
const candidates = await apiService.getCandidates();

// Upload de documento
const document = await apiService.uploadDocument(file, candidateId);

// Busca semântica
const results = await apiService.semanticSearch(query);
```

### WebSocket

Conexão WebSocket para atualizações em tempo real:

```typescript
import { websocketService } from './services/websocket';

// Conectar (feito automaticamente no login)
websocketService.connect(token);

// Subscrever a atualizações de documento
websocketService.subscribeDocument(documentId);

// Escutar eventos
websocketService.on('document_progress', (message) => {
  console.log(message.progress, message.status);
});
```

## 🎯 Rotas da Aplicação

| Rota | Componente | Descrição |
|------|-----------|-----------|
| `/login` | LoginPage | Página de login |
| `/register` | RegisterPage | Cadastro de usuário |
| `/dashboard` | DashboardPage | Dashboard principal |
| `/candidates` | CandidatesPage | Lista de candidatos |
| `/candidates/:id` | CandidateDetailPage | Detalhes do candidato |
| `/search` | SearchPage | Busca de candidatos |
| `/upload` | UploadPage | Upload de currículos |
| `/settings` | SettingsPage | Configurações do sistema |
| `/roles` | RolesPage | Gerenciamento de funções |

## 🔐 Autenticação

O sistema usa JWT (JSON Web Tokens) para autenticação:

1. Usuário faz login com email e senha
2. Backend retorna um `access_token`
3. Token é armazenado no `localStorage`
4. Todas as requisições incluem o token no header `Authorization: Bearer <token>`
5. WebSocket se conecta usando o token como query parameter

## 📊 Monitoramento em Tempo Real

O frontend recebe atualizações em tempo real via WebSocket:

- **Progresso de upload**: Status e porcentagem de processamento
- **Processamento de documentos**: Etapas do pipeline (OCR, parsing, embeddings)
- **Notificações do sistema**: Eventos importantes

## 🎨 Temas e Estilos

O frontend usa Material-UI com tema customizável:

```typescript
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});
```

## 🧪 Testes

```bash
# Executar testes
npm test

# Cobertura de testes
npm run test -- --coverage
```

## 📦 Build de Produção

```bash
# Criar build otimizado
npm run build

# Arquivos de produção estarão em /build
```

## 🐛 Troubleshooting

### Erro de CORS

Se encontrar erros de CORS, verifique se o backend está configurado corretamente:

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### WebSocket não conecta

Verifique:
1. Token JWT válido
2. URL do WebSocket correta (`ws://` ou `wss://`)
3. Backend WebSocket está rodando

### Componentes não renderizam

1. Limpe cache: `npm cache clean --force`
2. Delete `node_modules` e reinstale: `rm -rf node_modules && npm install`
3. Verifique versões do Node.js (recomendado: 18+)

## 📚 Recursos Adicionais

- [React Documentation](https://react.dev/)
- [Material-UI Documentation](https://mui.com/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [React Router](https://reactrouter.com/)

## 📝 Licença

MIT
