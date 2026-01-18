import { useCallback, useEffect, useState, DragEvent } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
} from '@xyflow/react';
import type { Connection, Node, Edge, NodeTypes } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { Topbar } from './components/Topbar';
import { Sidebar } from './components/Sidebar';
import { LogPanel } from './components/LogPanel';
import { InputNode } from './components/nodes/InputNode';
import { ExtractNode } from './components/nodes/ExtractNode';
import { ProcessNode } from './components/nodes/ProcessNode';
import { TranslateNode } from './components/nodes/TranslateNode';
import { ViewerNode } from './components/nodes/ViewerNode';
import { useFlowStore } from './store/flowStore';
import type { NodeData } from './types';
import { executeAllNodes } from './utils/execution';

const nodeTypes: NodeTypes = {
  input: InputNode,
  extract: ExtractNode,
  process: ProcessNode,
  translate: TranslateNode,
  viewer: ViewerNode,
};

// Initial demo flow
const initialNodes: Node<NodeData>[] = [
  {
    id: 'input-1',
    type: 'input',
    position: { x: 100, y: 200 },
    data: {
      label: 'Input',
      status: 'idle',
      config: { images: [] },
      logs: [],
    },
  },
  {
    id: 'extract-1',
    type: 'extract',
    position: { x: 500, y: 200 },
    data: {
      label: 'Extract',
      status: 'idle',
      config: { useGpu: true },
      logs: [],
    },
  },
  {
    id: 'process-1',
    type: 'process',
    position: { x: 900, y: 200 },
    data: {
      label: 'Process',
      status: 'idle',
      config: { similarityThreshold: 0.8, useLlm: false, llmModel: 'qwen2.5:7b' },
      logs: [],
    },
  },
  {
    id: 'translate-1',
    type: 'translate',
    position: { x: 1300, y: 200 },
    data: {
      label: 'Translate',
      status: 'idle',
      config: { backend: 'ollama', model: 'qwen2.5:7b', detailed: false },
      logs: [],
    },
  },
  {
    id: 'viewer-1',
    type: 'viewer',
    position: { x: 1700, y: 200 },
    data: {
      label: 'Viewer',
      status: 'idle',
      config: { searchQuery: '' },
      logs: [],
    },
  },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'input-1', target: 'extract-1', animated: true },
  { id: 'e2-3', source: 'extract-1', target: 'process-1', animated: true },
  { id: 'e3-4', source: 'process-1', target: 'translate-1', animated: true },
  { id: 'e4-5', source: 'translate-1', target: 'viewer-1', animated: true },
];

function App() {
  const [showLogs, setShowLogs] = useState(false);
  const {
    nodes,
    edges,
    setNodes,
    setEdges,
    updateNodeData,
    updateNodeStatus,
    updateNodeResult,
    addLog,
  } = useFlowStore();

  useEffect(() => {
    if (nodes.length === 0) {
      setNodes(initialNodes);
    }
    if (edges.length === 0) {
      setEdges(initialEdges);
    }
  }, [nodes.length, edges.length, setNodes, setEdges]);

  const handleNodesChange = useCallback((changes: any) => {
    setNodes(applyNodeChanges(changes, nodes));
  }, [setNodes, nodes]);

  const handleEdgesChange = useCallback((changes: any) => {
    setEdges(applyEdgeChanges(changes, edges));
  }, [setEdges, edges]);

  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdges = addEdge({ ...connection, animated: true }, edges);
      setEdges(newEdges);
    },
    [edges, setEdges]
  );

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow');
      if (!type) return;

      const position = { x: event.clientX - 200, y: event.clientY - 100 };

      const defaultConfigs: Record<string, any> = {
        input: { images: [] },
        extract: { useGpu: true },
        process: { similarityThreshold: 0.8, useLlm: false, llmModel: 'qwen2.5:7b' },
        translate: { backend: 'ollama', model: 'qwen2.5:7b', detailed: false },
        viewer: { searchQuery: '' },
      };

      const newNode: Node<NodeData> = {
        id: `${type}-${Date.now()}`,
        type,
        position,
        data: {
          label: type.charAt(0).toUpperCase() + type.slice(1),
          status: 'idle',
          config: defaultConfigs[type] || {},
          logs: [],
        },
      };

      setNodes([...nodes, newNode]);
    },
    [nodes, setNodes]
  );

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleRunAll = useCallback(async () => {
    if (nodes.length === 0) {
      addLog({
        nodeId: 'system',
        message: '実行するノードがありません',
        level: 'warning',
      });
      return;
    }

    try {
      await executeAllNodes(
        nodes,
        edges,
        updateNodeStatus,
        updateNodeResult,
        updateNodeData,
        addLog
      );
    } catch {
      // Errors are already logged inside executeAllNodes.
    }
  }, [nodes, edges, updateNodeStatus, updateNodeResult, updateNodeData, addLog]);

  return (
    <div className="h-screen flex flex-col bg-dark-bg">
      <Topbar onRunAll={handleRunAll} onToggleLogs={() => setShowLogs(!showLogs)} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar />

        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={onConnect}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            fitView
            className="bg-dark-bg"
          >
            <Background color="#2a2a2a" gap={20} size={1} variant={BackgroundVariant.Dots} />
            <Controls className="bg-dark-node border-dark-border" />
            <MiniMap
              className="bg-dark-node border-dark-border"
              nodeColor={(node) => {
                switch (node.data.status) {
                  case 'success': return '#00ffaa';
                  case 'error': return '#ff4444';
                  case 'running': return '#ffaa00';
                  default: return '#2d2d2d';
                }
              }}
            />
          </ReactFlow>
        </div>
      </div>

      <LogPanel isOpen={showLogs} onClose={() => setShowLogs(false)} />
    </div>
  );
}

export default App;
