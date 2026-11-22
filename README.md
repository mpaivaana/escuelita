# La Escuelita Ambiental Móvil

Site institucional com gestor de conteúdo (CMS).

| Parte | Tecnologia | Hospedagem |
|---|---|---|
| `frontend/` | Flask (páginas em es/en/pt) | Vercel |
| `backend/` | Django + DRF + Unfold (API e gestor) | Railway |
| Banco de dados | Postgres | Neon / Railway (`DATABASE_URL`) |
| Imagens | Cloudinary (`CLOUDINARY_URL`) | — |

O front busca o conteúdo em `GET {API_URL}/api/site/?lang=es|en|pt` e `/api/blog/`; o formulário de contato envia `POST /api/contact/` com a chave `X-Contact-Key`. Quem edita o conteúdo usa o gestor em `https://<backend>/<ADMIN_PATH>/`.

## Variáveis de ambiente

**Backend (Railway)**: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_URL`, `ADMIN_PATH`, `CONTACT_API_KEY`, `FRONTEND_URL`, `DJANGO_SUPERUSER_USERNAME/PASSWORD` (primeiro administrador), `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`. Opcionais, para receber cada mensagem do formulário por e-mail: `CONTACT_NOTIFY_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`. Modelo em `backend/.env.example`.

**Front (Vercel)**: `API_URL` (URL pública do backend; o front limpa aspas, espaços e caminhos extras), `CONTACT_API_KEY` (igual à do backend), `CONTENT_TTL` (opcional, padrão 5 s; se existir na Vercel com valor alto, como 60, reduza ou apague).

> Sem `CLOUDINARY_URL` as imagens vão para o disco do servidor e **se perdem a cada deploy**. Sem `DATABASE_URL` o backend usa SQLite, com o mesmo problema.

## Rodar localmente

```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env            # ajuste; sem DATABASE_URL usa SQLite
python manage.py migrate && python manage.py seed_content --images seed_images
python manage.py createsuperuser && python manage.py runserver 8000

# front (outro terminal)
cd frontend && pip install -r requirements.txt
API_URL=http://127.0.0.1:8000 python api/index.py     # http://localhost:5000
```

## Verificar

```bash
cd backend && python manage.py test                              # testes de regressão
python manage.py check_integrations --write-test --check-urls    # banco, Cloudinary, CMS, imagens (rode no Console da Railway)
python scripts/smoke_prod.py --front https://SEU-FRONT --api https://SEU-BACKEND --admin-path SEU_ADMIN_PATH
```

Se `API_URL` estiver errada ou ausente, **na Vercel** o front usa como reserva o backend de produção (`DEFAULT_API_URL` em `frontend/api/_content.py`; atualize se o domínio mudar) e avisa em `X-Content-Warning`. Se nenhum backend responder, o motivo vai em `X-Content-Error` e nos logs da Vercel. Testes do front: `cd frontend && python -m unittest discover -s tests`.

`check_integrations` e `smoke_prod.py` terminam com código 1 se algo falhar. O front informa de onde veio a página no cabeçalho `X-Content-Source` (`cms`, `degraded` = CMS fora do ar/`API_URL` errada, `seed` = modo dev sem backend).

## Notas de operação

- `seed_content` roda a cada deploy, mas só carrega dados se o banco estiver vazio. Para bases antigas sem equipe: `python manage.py seed_content --team`.
- Edições no gestor aparecem no site em poucos segundos (cache de ~5 s no front e no CDN). Nas listas editáveis (Publicado, Orden) é preciso clicar em **Guardar** para salvar.
- Os textos têm uma versão por idioma: editar só a aba Español muda só `/es/`; en e pt continuam com o texto que já tinham até serem editados (se estiverem vazios, usam o espanhol).
- Mensagens do formulário: em «Formulario de contacto» clique na linha para ler a mensagem completa e use «Responder por correo». Com `CONTACT_NOTIFY_EMAIL` e `EMAIL_HOST` definidos, cada mensagem também chega por e-mail (Reply-To = quem escreveu). Editores podem ler e marcar como respondida, não excluir (permissões em `content/migrations/0005_editors_group.py`).
- Papéis: **Editor/a** edita site e blog; **Administrador/a** também gerencia usuários.
