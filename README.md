# Documentando Algumas Requisições

## Criar um usuário

```bash
curl -X POST http://localhost:5001/register -H "Content-Type: application/json" -d '{"name": "João Silva", "email": "joao@example.com", "password": "senhaSegura123", "role": "user", "documentType": "cpf", "document": "12345678900"}'
```

## Fazer login

```bash
curl -X POST http://localhost:5001/login -H "Content-Type: application/json" -d '{"email": "joao@example.com", "password": "senhaSegura123"}'
```

## Criar um Ticket

```bash
curl -X POST http://localhost:5002/tickets   -H "Authorization: Bearer ${TOKEN}"   -F "title=buraco"   -F "description=buraco na rua"   -F "address=Rua Exemplo, 123"
```

## Deixar um Comentário em um Ticket

```bash
curl -X POST "http://localhost:5003/feedback"   -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" -d '{ "ticket_id": 1, "user_id": 3, "content": "Este buraco está muito grande, precisa de atenção urgente."}'
```

## Deletar um Comentário em um Ticket

```bash
curl -X DELETE "http://localhost:5003/feedback/1" -H "Authorization: Bearer ${TOKEN}"
```

## Alterar um Comentário em um Ticket

```bash
curl -X PATCH "http://localhost:5003/feedback/1" -H "Authorization: Bearer ${TOKEN}"  -H "Content-Type: application/json"   -d '{"content": "O buraco aumentou ainda mais de tamanho."}'
```

## Consultar Todos os Comentários

```bash
curl -X GET "http://localhost:5003/feedback"
```

## Consultar um dado Comentário

```bash
curl -X GET "http://localhost:5003/feedback/1"

curl -X GET "http://localhost:5003/feedback?ticket_id=1"
```
