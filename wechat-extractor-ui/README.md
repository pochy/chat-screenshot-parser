# WeChat Extractor - Node-Based UI

A professional node-based workflow editor for the WeChat Screenshot Conversation Extractor, built with React Flow.

## Features

- **Visual Workflow Editor**: Drag-and-drop node-based interface similar to ComfyUI/Blender
- **5 Custom Nodes**:
  - **Input Node**: Upload images with drag & drop and thumbnail preview
  - **Extract Node**: OCR extraction with GPU toggle
  - **Process Node**: Deduplication and refinement with LLM support
  - **Translate Node**: Multi-backend translation (Ollama/Gemini/Gemini Batch)
  - **Viewer Node**: Results viewer with search and export
- **Dark Theme**: Professional dark UI with accent colors
- **State Management**: Zustand for global state
- **Mock API**: Built-in mock mode for testing without backend
- **Flow Persistence**: Save/load flows to localStorage

## Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## Environment Variables

Create a `.env` file for real backend integration:

```env
VITE_API_URL=http://localhost:8000
```

If `VITE_API_URL` is not set, the app will use mock API mode.

## Usage

1. **Add Nodes**: Drag nodes from the sidebar or click to add
2. **Connect Nodes**: Drag from output handle to input handle
3. **Configure**: Click nodes to expand settings
4. **Execute**: Click the play button on each node or "Run All"
5. **View Logs**: Click "Logs" button in topbar
6. **Save/Load**: Save your workflow to localStorage

## Project Structure

```
src/
├── components/
│   ├── nodes/          # Custom node components
│   ├── Topbar.tsx      # Top navigation bar
│   ├── Sidebar.tsx     # Node palette
│   └── LogPanel.tsx    # Execution logs
├── store/
│   └── flowStore.ts    # Zustand state management
├── types/
│   └── index.ts        # TypeScript definitions
├── utils/
│   └── api.ts          # API calls (mock + real)
├── App.tsx             # Main React Flow canvas
└── main.tsx            # Entry point
```

## Backend Integration

The UI expects the following FastAPI endpoints:

- `POST /upload-images` - Upload images
- `POST /extract` - OCR extraction
- `POST /process` - Deduplication and refinement
- `POST /translate` - Translation

See `src/utils/api.ts` for request/response formats.

## License

MIT
