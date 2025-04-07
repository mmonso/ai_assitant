# Sugestões de Melhoria para o Projeto

## 1. Código (Boas Práticas, Limpeza, Refatoração)

*   **[CONCLUÍDO] Refatorar `routes/chat_api.py -> chat()`:**
    *   Quebrar a função `chat()` em funções menores com responsabilidade única (ex: `_preparar_payload_gemini`, `_buscar_ou_criar_conversa`, `_salvar_turno_chat`, `_gerar_titulo_conversa_se_necessario`).
*   **[CONCLUÍDO] Melhorar Tratamento de Erros e Logging:**
    *   [CONCLUÍDO] Substituir `print()` pelo módulo `logging` padrão do Python.
    *   [CONCLUÍDO] Capturar exceções mais específicas (ex: `sqlite3.OperationalError`).
    *   [CONCLUÍDO] Considerar levantar exceções customizadas em `db_utils.py` (Implementado: `DatabaseError`, `DuplicateUserError`, etc.).
    *   [CONCLUÍDO] Retornar mensagens de erro genéricas para o cliente e logar detalhes no servidor (Implementado nas rotas ao capturar exceções customizadas).
*   **[CONCLUÍDO] Mover Lógica de DB das Rotas:**
    *   [CONCLUÍDO] Criar funções em `db_utils.py` que encapsulem verificações de propriedade e operações de DB (ex: `delete_conversation(conversation_id, user_id)`).
*   **[CONCLUÍDO] Centralizar Configurações:**
    *   [CONCLUÍDO] Mover constantes (nome do modelo Gemini, nome do arquivo DB) para `config.py` ou variáveis de ambiente.
*   **[CONCLUÍDO] Remover Código de Teste de `db_utils.py`:**
    *   [CONCLUÍDO] Mover testes do bloco `if __name__ == '__main__':` para uma suíte de testes dedicada (ex: `pytest`). (Bloco comentado durante implementação do logging).
*   **[CONCLUÍDO] Revisar Redundâncias:**
    *   [CONCLUÍDO] Remover código duplicado (ex: linhas 194-195 em `chat_api.py`). (Verificado que foi corrigido em refatoração anterior).

## 2. Design (Ícones, Alinhamento, Cores - Sugestões Gerais)

*   **[CONCLUÍDO] Consistência Visual:** Garantir uniformidade em cores, fontes, espaçamentos e estilos de componentes entre todas as páginas. Usar variáveis CSS. (Verificado que `base.css` define variáveis e outros CSS as utilizam).
*   **[VERIFICADO] Hierarquia Visual Clara:** Usar tipografia (tamanho, peso, cor) para guiar o usuário. (CSS e HTML indicam uso de diferentes estilos para hierarquia).
*   **[CONCLUÍDO] Feedback Visual:** Fornecer indicações claras para ações do usuário (loading, sucesso, erro). (Implementado para envio de msg, CRUD de conversas, forms de settings, spinner de carregamento inicial).
*   **[CONCLUÍDO] Ícones:** Utilizar ícones SVG consistentes e significativos para ações comuns. (Substituído Unicode por SVGs inline).
*   **[PARCIALMENTE CONCLUÍDO] Alinhamento:** Verificar alinhamento em diferentes tamanhos de tela (responsividade) usando Flexbox/Grid. (Implementada responsividade básica da sidebar).
*   **Paleta de Cores:** Definir uma paleta coesa e acessível (verificar contraste).

## 3. Usabilidade (Como deixar o projeto mais agradável - Sugestões Gerais)

*   **[CONCLUÍDO] Feedback Imediato:** Informar o usuário sobre o status das operações (envio de mensagem, salvamento, etc.). (Adicionado spinner ao renomear conversa. Verificado: spinner já existe ao salvar configurações).
*   **[CONCLUÍDO] Tratamento de Erros no Frontend:** Capturar erros da API no JavaScript e mostrar mensagens amigáveis. (Padronizada exibição de erros no chat com mensagens genéricas; erros de formulário mantidos).
*   **[CONCLUÍDO] Configurações Claras:** Organizar a tela/modal de configurações de forma lógica e explicativa. (Adicionado help-text, padronizados títulos de seção).

## 4. Features (Como aprimorar com mais tecnologias - Sugestões)

*   **Streaming de Respostas:** Exibir respostas da IA em tempo real (SSE, WebSockets).
*   **Markdown Rendering:** Renderizar Markdown nas mensagens.
*   **Edição de Mensagens:** Permitir que usuários editem suas mensagens.
*   **Busca em Conversas:** Implementar busca no histórico.
*   **Compartilhamento de Conversas:** Gerar links públicos (somente leitura).
*   **Seleção de Modelo:** Permitir escolha do modelo de IA (se aplicável).
*   **Upload de Arquivos/Imagens:** Adicionar suporte a multimodalidade (se o modelo permitir).
*   **Temas Múltiplos:** Oferecer temas pré-definidos (claro/escuro) ou personalização.
*   **Exportação de Conversas:** Permitir exportar histórico (JSON, TXT, MD).
*   **Melhorias na Geração de Título:** Usar IA para gerar títulos mais contextuais.