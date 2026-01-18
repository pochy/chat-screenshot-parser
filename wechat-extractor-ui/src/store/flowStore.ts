import { create } from 'zustand';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData, LogEntry } from '../types';

interface FlowState {
    nodes: Node<NodeData>[];
    edges: Edge[];
    logs: LogEntry[];
    flowName: string;

    setNodes: (nodes: Node<NodeData>[]) => void;
    setEdges: (edges: Edge[]) => void;
    updateNodeData: (nodeId: string, data: Partial<NodeData>) => void;
    updateNodeStatus: (nodeId: string, status: NodeData['status']) => void;
    updateNodeResult: (nodeId: string, result: any) => void;
    addLog: (log: Omit<LogEntry, 'timestamp'>) => void;
    clearLogs: () => void;
    setFlowName: (name: string) => void;
    saveFlow: () => void;
    loadFlow: () => void;
}

export const useFlowStore = create<FlowState>((set, get) => ({
    nodes: [],
    edges: [],
    logs: [],
    flowName: 'Untitled Flow',

    setNodes: (nodes) => set({ nodes }),

    setEdges: (edges) => set({ edges }),

    updateNodeData: (nodeId, data) => set((state) => ({
        nodes: state.nodes.map((node) =>
            node.id === nodeId
                ? { ...node, data: { ...node.data, ...data } }
                : node
        ),
    })),

    updateNodeStatus: (nodeId, status) => set((state) => ({
        nodes: state.nodes.map((node) =>
            node.id === nodeId
                ? { ...node, data: { ...node.data, status } }
                : node
        ),
    })),

    updateNodeResult: (nodeId, result) => set((state) => ({
        nodes: state.nodes.map((node) =>
            node.id === nodeId
                ? { ...node, data: { ...node.data, result } }
                : node
        ),
    })),

    addLog: (log) => set((state) => {
        const entry = { ...log, timestamp: new Date().toISOString() };
        const nodes = log.nodeId === 'system'
            ? state.nodes
            : state.nodes.map((node) =>
                node.id === log.nodeId
                    ? {
                        ...node,
                        data: {
                            ...node.data,
                            logs: [...(node.data.logs || []), entry.message].slice(-5),
                        },
                    }
                    : node
            );

        return {
            logs: [...state.logs, entry],
            nodes,
        };
    }),

    clearLogs: () => set((state) => ({
        logs: [],
        nodes: state.nodes.map((node) => ({
            ...node,
            data: {
                ...node.data,
                logs: [],
            },
        })),
    })),

    setFlowName: (name) => set({ flowName: name }),

    saveFlow: () => {
        const { nodes, edges, flowName } = get();
        const flowData = { nodes, edges, flowName };
        localStorage.setItem('wechat-extractor-flow', JSON.stringify(flowData));
        get().addLog({
            nodeId: 'system',
            message: `Flow "${flowName}" saved successfully`,
            level: 'info',
        });
    },

    loadFlow: () => {
        const saved = localStorage.getItem('wechat-extractor-flow');
        if (saved) {
            const { nodes, edges, flowName } = JSON.parse(saved);
            set({ nodes, edges, flowName });
            get().addLog({
                nodeId: 'system',
                message: `Flow "${flowName}" loaded successfully`,
                level: 'info',
            });
        }
    },
}));
