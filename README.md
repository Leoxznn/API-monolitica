# Sistema monolítico com microserviços via HTTP real

Exemplo didático que demonstra como dividir responsabilidades entre três peças principais — Gateway, Monólito e PaymentService — com comunicação HTTP real usando Flask e Requests.

## Visão geral

- O **Gateway** recebe pedidos do cliente e encaminha para o Monólito.
- O **Monólito** contém a lógica de negócio (cria pedidos, aplica regras).
- O **PaymentService** decide se o pagamento é aprovado ou não.

A comunicação entre o Monólito e o PaymentService é feita por **HTTP real**: cada componente roda como um servidor Flask independente, em sua própria porta. Isso permite que, em produção, cada peça funcione em processos ou máquinas separadas sem mudança de código.

## Arquitetura

```
  Cliente
    │
    │ POST /api/orders  (HTTP :5000)
    ▼
  Gateway  :5000
    │
    │ chamada Python direta
    ▼
  Monólito
    │
    │ POST /payment  (HTTP :5001)
    ▼
  PaymentService  :5001
```

## Componentes

### Gateway — `gateway.py` `:5000`

Servidor Flask que expõe a rota `POST /api/orders`. Valida o body recebido (campos `item` e `price` são obrigatórios), registra logs e encaminha para o Monólito. Retorna erros em JSON para qualquer situação inválida (400, 404, 405).

### Monólito — `monolith.py`

Contém a lógica de domínio. O método `create_order(data)` monta o objeto do pedido e chama o PaymentService via `requests.post()` para processar o pagamento. Não conhece a implementação do PaymentService — apenas o contrato HTTP.

### PaymentService — `payment_service.py` `:5001`

Servidor Flask que expõe a rota `POST /payment`. Aprova pagamentos com `price > 0` e rejeita com `price == 0`. Em um produto real, teria integração com gateways de pagamento, tratamento de transações e controles de segurança.

### Outros arquivos

- `main.py` — sobe os dois servidores em threads e mantém o processo ativo.
- `logger_config.py` — configura o logging centralizado com formato `asctime [levelname] nome: mensagem`.

## Como executar

### Instalar dependências

```bash
pip install flask requests pytest
```

### Subir o servidor

```bash
python main.py
```

Saída esperada:
```
Gateway      → http://0.0.0.0:5000
PaymentSvc   → http://0.0.0.0:5001
Pressione Ctrl+C para encerrar.
```

### Fazer uma requisição de teste

```bash
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"item": "Mouse", "price": 50}'
```

Resposta esperada:
```json
{
  "order": { "id": 1, "item": "Mouse", "price": 50 },
  "payment_status": "APPROVED"
}
```

## Usando o Postman

Com o servidor rodando, configure uma requisição no Postman:

| Campo | Valor |
|---|---|
| Method | `POST` |
| URL | `http://localhost:5000/api/orders` |
| Header | `Content-Type: application/json` |
| Body (raw JSON) | `{"item": "Mouse", "price": 50}` |

Cenários para testar:
- `price > 0` → `APPROVED`
- `price = 0` → `REJECTED`
- Body sem `item` ou `price` → `400 Bad Request`
- Rota inexistente → `404 Not Found`
- Método errado (ex: GET em `/api/orders`) → `405 Method Not Allowed`

## Testes

O projeto tem dois tipos de teste:

**Unitários** (`tests/test_monolith.py`) — isolam o Monólito usando `unittest.mock.patch` para simular o `requests.post`. Não precisam de servidores rodando, são rápidos e determinísticos.

**Integração** (`tests/test_integration.py`) — fazem requisições HTTP reais contra os servidores. **Exigem que o `main.py` esteja rodando** em outro terminal antes de executar.

### Comandos

```bash
# Testes unitários (sem servidor)
python -m pytest tests/test_monolith.py -v

# Testes de integração (requer main.py rodando)
python -m pytest tests/test_integration.py -v

# Todos juntos
python -m pytest tests/test_monolith.py tests/test_integration.py -v
```

## Estrutura de arquivos

```
.
├── gateway.py                  # Servidor Flask :5000
├── monolith.py                 # Lógica de pedidos, chama PaymentService via HTTP
├── payment_service.py          # Servidor Flask :5001
├── main.py                     # Sobe os servidores e mantém o processo ativo
├── logger_config.py            # Configuração centralizada de logging
└── tests/
    ├── test_monolith.py        # Testes unitários com mock HTTP
    └── test_integration.py     # Testes de integração com servidores reais
```

## Considerações de design

A comunicação via HTTP desacopla completamente os serviços: o PaymentService pode ser reescrito em outra linguagem ou substituído por outro serviço, desde que respeite o contrato `POST /payment` com o JSON esperado.

Em um sistema real, vale considerar:

- **Timeouts** nas chamadas HTTP entre serviços para evitar travamentos em cascata.
- **Circuit breaker** para parar de chamar um serviço que está falhando repetidamente.
- **Confirmação de pagamento antes do pedido** (mais seguro) vs. aceitar o pedido e reconciliar depois (mais rápido, porém mais complexo).
- **Containerização** com Docker e orquestração com Docker Compose para facilitar o setup em diferentes ambientes.
