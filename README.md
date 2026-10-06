# Project Atlas

A collection of self-hosted open-source applications maintained in one workspace.

## Projects

| Project | Description | Start command | Log file |
| --- | --- | --- | --- |
| `image-service` | Command-line image processing and watermarking service | `cd projects/image-service && ./run.sh <command> [options]` | `projects/image-service/upstream/logs/app.log` |
| `openai-to-mcp` | Converts OpenAPI specifications into MCP servers | `cd projects/openai-to-mcp/upstream && npm run build && npm start` | `~/.openapi-mcp/logs/app-YYYY-MM-DD.log` |
| `visionary` | Multi-agent orchestration workspace | `cd projects/visionary/upstream && npm start` | `~/.visionary/server.log` |
| `parking-lot` | Parking operations API: check-ins, check-outs, tariffs and reports | `cd projects/parking-lot/upstream && uvicorn app.main:app` | stdout, or `LOG_FILE` with `LOG_FORMAT=json` |
| `shorty-url` | URL shortener with analytics and an administration console | `cd projects/shorty-url/upstream/server && npm run dev` | `projects/shorty-url/upstream/server/logs/app.log` |

Each project keeps its source in `upstream/` and records its origin, revision, license, and common commands in `project.json`.

## Shorty URL

Shorty URL contains two applications and requires Node.js plus MySQL 8 or TiDB.

```sh
cd projects/shorty-url/upstream/server
npm install
cp .env.example .env
# configure the database and ADMIN_JWT_SECRET in .env
npm run db:setup
npm run admin:create
npm run dev
```

In another terminal:

```sh
cd projects/shorty-url/upstream/frontend
npm install
cp .env.example .env.local
npm run dev
```

The API runs on `http://localhost:8080` and the web application runs on `http://localhost:3000` by default.
