# Sistema de Laudos

Sistema para gerenciamento e criação de laudos médicos com suporte a transcrição de voz e templates personalizáveis.

## Funcionalidades

- Criação e edição de laudos
- Transcrição de voz para texto
- Templates personalizáveis
- Gerenciamento de frases e modelos
- Exportação para DOCX
- Interface responsiva

## Tecnologias

- React
- Vite
- Mantine UI
- TipTap Editor
- Axios
- JWT Authentication

## Requisitos

- Node.js 18+
- npm ou yarn

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/laudos-frontend.git
cd laudos-frontend
```

2. Instale as dependências:
```bash
npm install
```

3. Configure as variáveis de ambiente:
```bash
cp .env.example .env
```

4. Inicie o servidor de desenvolvimento:
```bash
npm run dev
```

## Scripts Disponíveis

- `npm run dev` - Inicia o servidor de desenvolvimento
- `npm run build` - Gera o build de produção
- `npm run preview` - Previa o build de produção
- `npm run lint` - Executa o linter
- `npm run deploy:test` - Gera build e serve localmente
- `npm run deploy:prod` - Gera build e faz deploy

## Deploy

O projeto está configurado para deploy no Vercel. Para fazer o deploy:

1. Conecte seu repositório ao Vercel
2. Configure as variáveis de ambiente:
   - `VITE_API_URL` - URL da API
   - `VITE_APP_NAME` - Nome da aplicação
   - `VITE_APP_VERSION` - Versão da aplicação

## Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT.
