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

**Backend (Railway)**: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_URL`, `ADMIN_PATH`, `CONTACT_API_KEY`, `FRONTEND_URL`, `DJANGO_SUPERUSER_USERNAME/PASSWORD` (primeiro administrador), `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`. Modelo em `backend/.env.example`.

**Front (Vercel)**: `API_URL` (URL pública do backend, sem barra final), `CONTACT_API_KEY` (igual à do backend), `CONTENT_TTL` (opcional, padrão 60 s).

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

`check_integrations` e `smoke_prod.py` terminam com código 1 se algo falhar. O front informa de onde veio a página no cabeçalho `X-Content-Source` (`cms`, `degraded` = CMS fora do ar/`API_URL` errada, `seed` = modo dev sem backend).

## Notas de operação

- `seed_content` roda a cada deploy, mas só carrega dados se o banco estiver vazio. Para bases antigas sem equipe: `python manage.py seed_content --team`.
- Edições no gestor aparecem no site em cerca de 1 minuto (cache do CDN e do front).
- Papéis: **Editor/a** edita site e blog; **Administrador/a** também gerencia usuários.
