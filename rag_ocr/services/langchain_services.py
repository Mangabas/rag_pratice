from django.conf import settings

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage

from pgvector.django import CosineDistance
from rag_ocr.models import DocumentChunk


class LangchainServices:
    """
    Serviço RAG para análise de documentos jurídicos.

    Utiliza Google Gemini via LangChain para:
    - Gerar embeddings de texto (GoogleGenerativeAIEmbeddings)
    - Responder perguntas com contexto recuperado (ChatGoogleGenerativeAI)
    - Processar imagens de documentos escaneados (Gemini Vision multimodal)

    Variáveis de ambiente necessárias (via .env):
        GOOGLE_API_KEY: chave da API Google AI Studio
    """

    _EMBEDDING_MODEL = "gemini-embedding-001"
    _CHAT_MODEL = "gemini-3.6-flash"
    _EMBEDDING_DIMENSION = 768
    _TOP_K = 6
    _TEMPERATURE = 0.2

    def __init__(self):
        api_key = getattr(settings, "GOOGLE_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY não encontrada nas configurações. "
                "Adicione a chave no arquivo .env do projeto."
            )

        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=self._EMBEDDING_MODEL,
            google_api_key=api_key,
        )

        self._llm = ChatGoogleGenerativeAI(
            model=self._CHAT_MODEL,
            google_api_key=api_key,
            temperature=self._TEMPERATURE,
        )

    # ------------------------------------------------------------------
    # Prompt do sistema
    # ------------------------------------------------------------------

    def _prompt_system(self) -> SystemMessage:
        conteudo = (
            "Você é um assistente especialista em análise de documentos jurídicos.\n"
            "Seu papel é ajudar advogados, operadores jurídicos e recepcionistas a "
            "extrair informações e interpretar documentos com clareza e precisão.\n"
            "\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. Responda SOMENTE com base no contexto fornecido. Nunca invente informações.\n"
            "1a. Se houver uma pergunta anterior do usuário no histórico, use-a apenas para interpretar "
            "a intenção da pergunta atual (ex.: pronomes, referências implícitas). "
            "A busca no contexto é sempre feita pela pergunta atual — não expanda nem repita a pergunta "
            "anterior na busca.\n"
            "2. Se o contexto trouxer MAIS DE UMA forma de realizar a operação, apresente TODAS as "
            "opções de forma clara e numerada.\n"
            "3. Se a pergunta for ampla ou genérica, examine TODO o contexto fornecido em busca de "
            "formas complementares de realizar a operação. Se encontrar trechos de documentos diferentes "
            "que, juntos, descrevem abordagens distintas para o mesmo objetivo, SINTETIZE-os em uma "
            "resposta unificada apresentando cada abordagem como uma opção numerada.\n"
            "4. Se realmente não houver NENHUMA informação relacionada ao tema no contexto, diga: "
            "'Não encontrei essa informação na base de conhecimento. Por favor, especifique melhor a "
            "pergunta ou entre em contato com o suporte.'\n"
            "5. Sempre indique a fonte da resposta ao final, no formato: 'Fonte: nome-do-arquivo'.\n"
            "\n"
            "FORMATAÇÃO DA RESPOSTA (siga rigorosamente):\n"
            "- Português do Brasil, linguagem simples e direta.\n"
            "- Para títulos de seção ou opções use o formato: ## Titulo da seção\n"
            "- Para passos numerados use: 1. Passo um\n"
            "- Para sub-itens de um passo use: - sub-item\n"
            "- Para destacar um termo importante use: **termo importante**\n"
            "- Separe blocos distintos com uma linha em branco.\n"
            "- Não use tabelas, não use underline, não use HTML.\n"
            "- Seja objetivo: responda o que foi perguntado sem rodeios.\n"
        )
        return SystemMessage(content=conteudo)

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed_query(self, quest: str) -> list:
        """Gera o vetor de embedding para a pergunta do usuário."""
        return self._embeddings.embed_query(quest)

    # ------------------------------------------------------------------
    # Busca semântica no banco (pgvector)
    # ------------------------------------------------------------------

    def _chunks_search(self, quest: str) -> list:
        """Busca os chunks mais relevantes via similaridade de cosseno."""
        if not quest or not quest.strip():
            raise ValueError(
                "Você não fez nenhuma pergunta. "
                "Em caso de dúvidas, pode digitar alguma pergunta!"
            )

        vector = self._embed_query(quest)
        if len(vector) > 768:
            vector = vector[:768]
            
        return list(
            DocumentChunk.objects.select_related("document").order_by(
                CosineDistance("embedding", vector)
            )[: self._TOP_K]
        )

    # ------------------------------------------------------------------
    # Montagem de mensagens
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        contexto: str,
        quest: str,
        imagem_base64: str = "",
    ) -> list:
        """
        Monta a lista de mensagens para o LLM.

        Args:
            contexto: Trechos recuperados do banco de vetores.
            quest: Pergunta atual do usuário.
            imagem_base64: Imagem em base64 para análise multimodal (OCR).
                           Deve estar no formato "data:image/jpeg;base64,<dados>"
                           ou apenas os dados base64 puros.

        Returns:
            Lista de mensagens no formato LangChain.
        """
        messages = [self._prompt_system()]

        # Mensagem final: contexto + pergunta (+ imagem opcional)
        texto_final = f"Contexto:\n{contexto}\n\nPergunta: {quest}"

        if imagem_base64:
            # Garante o prefixo correto para o formato data URI
            if not imagem_base64.startswith("data:"):
                imagem_base64 = f"data:image/jpeg;base64,{imagem_base64}"

            messages.append(
                HumanMessage(
                    content=[
                        {"type": "text", "text": texto_final},
                        {
                            "type": "image_url",
                            "image_url": {"url": imagem_base64},
                        },
                    ]
                )
            )
        else:
            messages.append(HumanMessage(content=texto_final))

        return messages

    # ------------------------------------------------------------------
    # Chat completion
    # ------------------------------------------------------------------

    def _chat_completion(
        self,
        contexto: str,
        quest: str,
        imagem_base64: str = "",
    ) -> str:
        """Invoca o LLM com o contexto e retorna a resposta em texto."""
        messages = self._build_messages(contexto, quest, imagem_base64=imagem_base64)
        response = self._llm.invoke(messages)
        return response.content

    # ------------------------------------------------------------------
    # Orquestração principal
    # ------------------------------------------------------------------

    def _get_question(
        self,
        quest: str,
        imagem_base64: str = "",
    ) -> dict:
        """
        Orquestra o pipeline RAG completo:
        1. Busca semântica dos chunks relevantes
        2. Monta o contexto
        3. Gera a resposta via LLM

        Returns:
            dict com 'resposta' (str) e 'fontes' (list[str])
        """
        chunks = self._chunks_search(quest)

        contexto = "\n\n".join(
            f"[Fonte: {chunk.document.file_name}]\n{chunk.content}" for chunk in chunks
        )
        fontes = list({chunk.document.file_name for chunk in chunks})

        resposta = self._chat_completion(
            contexto,
            quest,
            imagem_base64=imagem_base64,
        )

        return {
            "resposta": resposta,
            "fontes": fontes,
            "chunks": chunks,
        }

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def perguntar(self, quest: str) -> dict:
        """
        Responde uma pergunta textual usando o pipeline RAG.

        Args:
            quest: Pergunta do usuário.

        Returns:
            dict com 'resposta' (str) e 'fontes' (list[str])
        """
        return self._get_question(quest)

    def perguntar_com_imagem(
        self,
        imagem_base64: str,
        quest: str,
    ) -> dict:
        """
        Analisa um documento escaneado (imagem) e responde a pergunta.

        Usa a capacidade multimodal do Gemini Vision para realizar OCR
        e interpretação jurídica diretamente sobre a imagem do documento,
        sem necessidade de um step separado de OCR.

        Args:
            imagem_base64: Imagem do documento em base64.
                           Aceita formato data URI ("data:image/jpeg;base64,...")
                           ou base64 puro.
            quest: Pergunta sobre o documento (ex.: "Qual é o número do processo?").

        Returns:
            dict com 'resposta' (str) e 'fontes' (list[str])

        Exemplo de uso:
            import base64

            with open("contrato.jpg", "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            service = LangchainServices()
            resultado = service.perguntar_com_imagem(
                imagem_base64=img_b64,
                quest="Quais são as partes envolvidas neste contrato?",
            )
            print(resultado["resposta"])
        """
        return self._get_question(
            quest,
            imagem_base64=imagem_base64,
        )
