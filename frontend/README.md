# Kairos Stage 1 Frontend (M5)

Technical investigation cockpit for Kairos temporal lineage and evidence exploration.

## Stack
- **Framework**: React 18 + TypeScript (Strict mode)
- **Bundler & Dev Server**: Vite
- **Styling**: Tailwind CSS (Kairos dark forensic palette)
- **Graph Visualization**: `@xyflow/react` (React Flow)
- **Layout Engine**: `@dagrejs/dagre`
- **State Management**: `@tanstack/react-query`

## Architectural Guarantees
- Talks to `/api/v1` exclusively. Never accesses databases or reasoning internals directly.
- Multi-redundant reasoning states (glyph + pattern + border + text label; never color alone).
- Two separate bitemporal controls: `Valid at (T_v)` and `Known as of (T_k)`. Never merged into a single picker.
- Strict isolation of Benchmark Evaluation Mode (hazard tape banner and oracle inspection).
- No numerical confidence values or probabilities.

## Running the Frontend

### Development Mode (with hot-reload)
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Production Build
```bash
cd frontend
npm run build
```
The compiled bundle will be output to `frontend/dist/` and automatically served by FastAPI at `http://127.0.0.1:8000/`.
